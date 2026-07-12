"""
Geometry and Coordinate Helper Functions for Cattle Tracking Tool.
"""

import math
import json
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPolygonF


def display_to_image(dx, dy, display_offset, display_scale):
    ix = (dx - display_offset.x()) * display_scale
    iy = (dy - display_offset.y()) * display_scale
    return ix, iy


def polygon_from_points(pts):
    return QPolygonF([QPointF(p[0], p[1]) for p in pts])


def calculate_centroid(pts):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return cx, cy


def rotate_points(pts, angle_deg):
    cx, cy = calculate_centroid(pts)
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    new_pts = []
    for p in pts:
        dx, dy = p[0] - cx, p[1] - cy
        new_pts.append(
            [
                cx + dx * cos_a - dy * sin_a,
                cy + dx * sin_a + dy * cos_a,
            ]
        )
    return new_pts


def hit_test(ix, iy, cow_boxes):
    pt = QPointF(ix, iy)
    for i, cow in enumerate(cow_boxes):
        if len(cow["points"]) == 4:
            if polygon_from_points(cow["points"]).containsPoint(
                pt, Qt.FillRule.OddEvenFill
            ):
                return i
    return -1


def save_cow_json(json_path, cow_boxes):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create a lookup dictionary of group_id -> points for modified cow boxes
        cow_lookup = {str(box["id"]): box["points"] for box in cow_boxes}

        modified = False
        for shape in data.get("shapes", []):
            if shape.get("label") == "cow":
                group_id = str(shape.get("group_id", "Unknown"))
                if group_id in cow_lookup:
                    shape["points"] = cow_lookup[group_id]
                    modified = True

        if modified:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False
    return False
