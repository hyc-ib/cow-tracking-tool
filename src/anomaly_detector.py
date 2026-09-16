"""
Cattle Tracklet Anomaly Detector
=================================
Scans all JSON files under a directory and flags three categories of tracking errors:

  Rule 1 — ID_SWAP:               Two cows in adjacent frames have centroids that are very close, but carry different IDs.
  Rule 2 — UNREALISTIC_JUMP:      A single cow's centroid moves faster than a configurable velocity threshold between frames.
  Rule 3 — GEOMETRIC_DEFORMATION: A single cow's bounding box changes its rotation angle or area dramatically in one step.

Folder structure expected:
  json/
    └── <128>camera_json/
        └── <20250910T054822_20250910T060922>/
            └── <20250910T054822_20250910T060922_frame_0425>.json
            └── <20250910T054822_20250910T060922_frame_0475>.json
        └── <20250910T060922_20250910T063022>/
            └── <20250910T060922_20250910T063022_frame_0375>.json
            └── <20250910T060922_20250910T063022_frame_0775>.json
    └── <133>camera_json/
        └── <20250910T082911_20250910T085330>/
            └── <20250910T082911_20250910T085330_frame_0200>.json
            └── <20250910T082911_20250910T085330_frame_0875>.json
        └── <20250910T100443_20250910T102601>/
            └── <20250910T100443_20250910T102601_frame_0275>.json
            └── <20250910T100443_20250910T102601_frame_0900>.json

Output
------
json/anomalies.json

Usage
-----
  python src/anomaly_detector.py --json_root "path/to/json/"

Optional flags (all have sensible defaults):
  --fps              Annotation frame rate          (default 16.2)
  --id_swap_dist     Centroid-distance threshold    (default 60 px)
  --max_velocity     Max allowed speed              (default 300 px/s)
  --max_delta_theta  Max allowed angle jump         (default 45 deg)
  --max_area_ratio   Max allowed area change ratio  (default 0.5 = 50%)
"""

import argparse
import datetime
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


# ====================
# JSON helpers
# ====================
def load_session_frames(session_path: Path) -> dict:
    """
    Read every JSON file in *session_path* and return a dict:
        { frame_no (int) : [ {"id": ..., "points": [[x,y],...]} ] }

    Files are expected to contain LabelMe-style JSON with:
        shapes[].label     == "cow"
        shapes[].group_id  == integer cow ID
        shapes[].points    == list of 4 [x, y] pairs
    """
    frames: dict = {}
    for json_path in sorted(session_path.glob("*.json")):
        m = re.search(r"frame_(\d+)", json_path.stem)
        if not m:
            continue
        frame_no = int(m.group(1))
        try:
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            print(f"    [WARN] Cannot read {json_path.name}: {exc}")
            continue

        cows = [
            {
                "id": shape.get("group_id"),
                "points": shape.get("points", []),
            }
            for shape in data.get("shapes", [])
            if shape.get("label") == "cow"
        ]
        frames[frame_no] = cows

    return frames


# ====================
# Geometry utilities
# ====================
def centroid(points: list) -> tuple:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    return sum(xs) / n, sum(ys) / n


def bbox_geometry(points: list):
    """
    Return (area, theta_deg) for a 4-point bounding box.
    Uses cv2.minAreaRect so that angle is consistent.
    Returns (None, None) if points are invalid.
    """
    if len(points) != 4:
        return None, None
    pts = np.array(points, dtype=np.float32)
    try:
        _, (w, h), theta = cv2.minAreaRect(pts)
    except Exception:
        return None, None
    return w * h, theta


# ====================
# Rule 1 — ID_SWAP
# ====================
def rule1_id_swap(frames: dict, threshold_px: float = 60.0) -> list:
    """
    For every pair of consecutive annotated frames, check whether any two
    bounding boxes (with *different* IDs) have centroids closer than
    *threshold_px*.  This indicates the tracker swapped identities.

    Returns a list of anomaly dicts.
    """
    anomalies = []
    frame_keys = sorted(frames.keys())

    for i in range(len(frame_keys) - 1):
        prev_cows = frames[frame_keys[i]]
        curr_cows = frames[frame_keys[i + 1]]

        for c_prev in prev_cows:
            if not c_prev["points"]:
                continue
            cx0, cy0 = centroid(c_prev["points"])

            for c_curr in curr_cows:
                if c_curr["id"] == c_prev["id"]:
                    continue  # same ID → not a swap
                if not c_curr["points"]:
                    continue

                cx1, cy1 = centroid(c_curr["points"])
                dist = math.hypot(cx1 - cx0, cy1 - cy0)

                if dist < threshold_px:
                    anomalies.append(
                        {
                            "frame": frame_keys[i + 1],
                            "type": "ID_SWAP",
                            "ids": [c_prev["id"], c_curr["id"]],
                            "description": f"IDs {c_prev['id']} & {c_curr['id']} centroids close ({dist:.1f}px)",
                            "distance_px": round(dist, 1),
                        }
                    )

    return anomalies


# ====================
# Rule 2 — UNREALISTIC_JUMP
# ====================
def rule2_velocity_jump(
    frames: dict,
    fps: float = 16.2,
    max_velocity: float = 300.0,
) -> list:
    """
    For each cow ID, compute centroid displacement between consecutive
    annotated frames and derive a speed in px/s.  Flag any step that
    exceeds *max_velocity*.

    Returns a list of anomaly dicts.
    """
    anomalies = []

    # Build per-ID position timeline: {id: [(frame_no, cx, cy), ...]}
    id_positions: dict = defaultdict(list)
    for frame_no in sorted(frames.keys()):
        for cow in frames[frame_no]:
            if not cow["points"]:
                continue
            cx, cy = centroid(cow["points"])
            id_positions[cow["id"]].append((frame_no, cx, cy))

    for cow_id, positions in id_positions.items():
        for i in range(len(positions) - 1):
            f0, x0, y0 = positions[i]
            f1, x1, y1 = positions[i + 1]

            frame_gap = f1 - f0
            if frame_gap <= 0:
                continue
            time_gap = frame_gap / fps  # seconds

            distance = math.hypot(x1 - x0, y1 - y0)
            velocity = distance / time_gap  # px/s

            if velocity > max_velocity:
                anomalies.append(
                    {
                        "frame": f1,
                        "type": "UNREALISTIC_JUMP",
                        "id": cow_id,
                        "description": f"ID {cow_id} speed {velocity:.1f} px/s (max {max_velocity})",
                        "velocity_pps": round(velocity, 1),
                        "frame_gap": frame_gap,
                    }
                )

    return anomalies


# ====================
# Rule 3 — GEOMETRIC_DEFORMATION
# ====================
def rule3_geometric_deformation(
    frames: dict,
    max_delta_theta: float = 45.0,
    max_area_ratio: float = 0.5,
) -> list:
    """
    For each cow ID, compare the bounding-box geometry (area, rotation angle)
    between consecutive annotated frames.  Flag sudden changes.

    *max_delta_theta*  — maximum allowed angle change in degrees.
    *max_area_ratio*   — maximum allowed fractional area change (0.5 = 50 %).

    Returns a list of anomaly dicts.
    """
    anomalies = []
    # Last known geometry per ID: {id: (area, theta, frame_no)}
    prev_geom: dict = {}

    for frame_no in sorted(frames.keys()):
        for cow in frames[frame_no]:
            area, theta = bbox_geometry(cow["points"])
            if area is None:
                continue

            cow_id = cow["id"]
            if cow_id in prev_geom:
                prev_area, prev_theta, _ = prev_geom[cow_id]

                # Angle delta — handle 180-degree wrap (minAreaRect range)
                delta_theta = abs(theta - prev_theta)
                if delta_theta > 90:
                    delta_theta = 180.0 - delta_theta

                # Area change as a fraction of the previous area
                area_change = abs(area - prev_area) / max(prev_area, 1.0)

                if delta_theta > max_delta_theta or area_change > max_area_ratio:
                    anomalies.append(
                        {
                            "frame": frame_no,
                            "type": "GEOMETRIC_DEFORMATION",
                            "id": cow_id,
                            "description": f"ID {cow_id} Δθ={delta_theta:.1f}°, ΔArea={area_change * 100:.1f}%",
                            "delta_theta_deg": round(delta_theta, 1),
                            "area_change_ratio": round(area_change, 3),
                        }
                    )

            prev_geom[cow_id] = (area, theta, frame_no)

    return anomalies


# ====================
# Session and camera processing
# ====================
def process_session(session_path: Path, fps: float, thresholds: dict) -> dict:
    """Run all rules on a single timestamp session folder."""
    frames = load_session_frames(session_path)
    if not frames:
        return {"frame_count": 0, "anomaly_count": 0, "anomalies": []}

    anomalies = []
    anomalies += rule1_id_swap(frames, threshold_px=thresholds["id_swap_dist"])
    anomalies += rule2_velocity_jump(
        frames, fps=fps, max_velocity=thresholds["max_velocity"]
    )
    anomalies += rule3_geometric_deformation(
        frames,
        max_delta_theta=thresholds["max_delta_theta"],
        max_area_ratio=thresholds["max_area_ratio"],
    )

    # Sort by frame number for readability
    anomalies.sort(key=lambda a: a["frame"])

    return {
        "frame_count": len(frames),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }


def process_camera(camera_path: Path, fps: float, thresholds: dict) -> dict:
    """Process all session sub-folders found under a camera folder."""
    camera_results = {}
    session_dirs = sorted(d for d in camera_path.iterdir() if d.is_dir())

    for session_dir in session_dirs:
        result = process_session(session_dir, fps, thresholds)
        camera_results[session_dir.name] = result
        print(
            f"    {session_dir.name}: "
            f"{result['frame_count']} frames, "
            f"{result['anomaly_count']} anomalies"
        )

    return camera_results


# ====================
# Entry point
# ====================
def main():
    parser = argparse.ArgumentParser(
        description="Cattle Tracklet Anomaly Detector — scans all cameras automatically."
    )
    parser.add_argument(
        "--json_root",
        required=True,
        help="Root directory that contains all camera JSON folders.",
    )
    parser.add_argument(
        "--fps", type=float, default=16.2, help="Annotation FPS (default 16.2)"
    )
    parser.add_argument(
        "--id_swap_dist",
        type=float,
        default=60.0,
        help="ID-swap centroid-distance threshold in px (default 60)",
    )
    parser.add_argument(
        "--max_velocity",
        type=float,
        default=300.0,
        help="Max allowed velocity in px/s (default 300)",
    )
    parser.add_argument(
        "--max_delta_theta",
        type=float,
        default=45.0,
        help="Max allowed angle change in degrees (default 45)",
    )
    parser.add_argument(
        "--max_area_ratio",
        type=float,
        default=0.5,
        help="Max allowed area-change ratio (default 0.5 = 50%%)",
    )
    args = parser.parse_args()

    json_root = Path(args.json_root)
    if not json_root.exists():
        print(f"[ERROR] Directory not found: {json_root}")
        return

    thresholds = {
        "id_swap_dist": args.id_swap_dist,
        "max_velocity": args.max_velocity,
        "max_delta_theta": args.max_delta_theta,
        "max_area_ratio": args.max_area_ratio,
    }

    # Auto-discover camera folders (any direct subdirectory)
    camera_dirs = sorted(d for d in json_root.iterdir() if d.is_dir())
    if not camera_dirs:
        print("[ERROR] No sub-folders found in json_root.")
        return

    print(f"Found {len(camera_dirs)} camera folder(s):")
    for d in camera_dirs:
        print(f"  {d.name}")
    print()

    all_results = {}
    for camera_dir in camera_dirs:
        print(f"Processing camera: {camera_dir.name}")
        all_results[camera_dir.name] = process_camera(camera_dir, args.fps, thresholds)
        print()

    # Summary
    total_anomalies = sum(
        session["anomaly_count"]
        for cam in all_results.values()
        for session in cam.values()
    )

    output = {
        "generated_at": datetime.datetime.now().isoformat(),
        "annotation_fps": args.fps,
        "thresholds": thresholds,
        "total_anomalies": total_anomalies,
        "cameras": all_results,
    }

    out_path = json_root / "anomalies.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    print(f"Done. {total_anomalies} total anomalies detected.")
    print(f"Output → {out_path}")


if __name__ == "__main__":
    main()
