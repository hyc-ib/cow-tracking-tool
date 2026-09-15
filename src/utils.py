"""
Geometry and Coordinate Helper Functions for Cattle Tracking Tool.
"""

import json
import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainter, QPixmap, QPolygonF, QTransform


def crop_and_derotate_bbox(pixmap, points, force_horizontal=True):
    if not pixmap or len(points) != 4:
        return None

    x0, y0 = points[0]
    x1, y1 = points[1]
    x2, y2 = points[2]

    cx = sum(p[0] for p in points) / 4.0
    cy = sum(p[1] for p in points) / 4.0
    w = math.hypot(x1 - x0, y1 - y0)
    h = math.hypot(x2 - x1, y2 - y1)

    if w < 1 or h < 1:
        return None

    theta_rad = math.atan2(y1 - y0, x1 - x0)
    theta_deg = math.degrees(theta_rad)

    # Ensure the longest dimension (cow body length) is aligned horizontally
    if force_horizontal and h > w:
        theta_deg += 90.0
        w, h = h, w

    crop_w = max(1, round(w))
    crop_h = max(1, round(h))

    cropped = QPixmap(crop_w, crop_h)
    cropped.fill(Qt.GlobalColor.transparent)

    painter = QPainter(cropped)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setTransform(
        QTransform()
        .translate(crop_w / 2.0, crop_h / 2.0)
        .rotate(-theta_deg)
        .translate(-cx, -cy)
    )
    painter.drawPixmap(0, 0, pixmap)
    painter.end()

    return cropped


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
        if len(cow["points"]) == 4 and polygon_from_points(cow["points"]).containsPoint(
            pt, Qt.FillRule.OddEvenFill
        ):
            return i
    return -1


def save_cow_json(json_path, cow_boxes):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Build lookups
        cow_lookup = {str(box["id"]): box["points"] for box in cow_boxes}

        # Track which IDs already exist in JSON
        existing_ids_in_json = {
            str(s.get("group_id", ""))
            for s in data.get("shapes", [])
            if s.get("label") == "cow"
        }

        # Update or Delete existing shapes
        updated_shapes = []
        for shape in data.get("shapes", []):
            if shape.get("label") != "cow":
                updated_shapes.append(shape)  # preserve non-cow shapes
                continue
            gid = str(shape.get("group_id", ""))
            if gid in cow_lookup:
                shape["points"] = cow_lookup[gid]
                updated_shapes.append(shape)
            # else: this cow was deleted (omit it)

        # Append brand-new cows not yet in the JSON
        for box in cow_boxes:
            if str(box["id"]) not in existing_ids_in_json:
                updated_shapes.append(
                    {
                        "label": "cow",
                        "points": box["points"],
                        "group_id": box["id"],
                        "shape_type": "polygon",
                        "flags": {},
                    }
                )

        data["shapes"] = updated_shapes
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False
