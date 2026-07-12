"""
Cattle Tracklet Merge Assistant (Frame Edition)

Folder structure expected:
  <camera1>/
    └── frames/
        └── <20250910T054951_20250910T061053>/
            └── <20250910T054951_20250910T061053_frame_0050>.jpg
            └── <20250910T054951_20250910T061053_frame_0075>.jpg
        └── <20250910T061053_20250910T063156>/
            └── <20250910T061053_20250910T063156_frame_0025>.jpg
            └── <20250910T061053_20250910T063156_frame_0050>.jpg
    └── <1camera>-json.zip
"""

import sys
import os
import json
import zipfile
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QLabel,
    QPushButton,
    QFileDialog,
    QSizePolicy,
    QComboBox,
    QLineEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QIntValidator

import utils


class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._on_press = None
        self._on_move = None
        self._on_release = None

    def set_callbacks(self, on_press, on_move, on_release):
        self._on_press = on_press
        self._on_move = on_move
        self._on_release = on_release

    def mousePressEvent(self, event):
        if self._on_press and event.button() == Qt.MouseButton.LeftButton:
            self._on_press(event.position().x(), event.position().y())

    def mouseMoveEvent(self, event):
        if self._on_move:
            is_pressed = bool(event.buttons() & Qt.MouseButton.LeftButton)
            self._on_move(event.position().x(), event.position().y(), is_pressed)

    def mouseReleaseEvent(self, event):
        if self._on_release and event.button() == Qt.MouseButton.LeftButton:
            self._on_release()


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_frames = []
        self.base_folder_path = None
        self.temp_json_dir = None

        # Editing state
        self.cow_boxes = []
        self.selected_cow_idx = -1  # nothing selected
        self.drag_start_img = None
        self.drag_start_points = None
        self.is_dragging = False
        self.has_unsaved_changes = False
        self.current_index = 0

        # Display state
        self.original_pixmap = None
        self.display_scale = 1.0  # image_pixels / display_pixel
        self.display_offset = QPointF(0, 0)

        self.setWindowTitle("Cattle Tracklet Merge Assistant - Frame Edition")
        self.setGeometry(100, 100, 1000, 700)

        # Widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top Bar
        top_bar = QHBoxLayout()
        self.btn_open = QPushButton("Open Folder")
        self.btn_open.setStyleSheet(
            "font-size: 14px; padding: 8px 18px;"
            "background-color: #005088; color: white; border-radius: 5px;"
        )
        self.btn_open.clicked.connect(self.select_folder)
        top_bar.addWidget(self.btn_open)

        top_bar.addWidget(QLabel("Select Timestamp:"))
        self.combo_timestamp = QComboBox()
        self.combo_timestamp.setMinimumWidth(300)
        self.combo_timestamp.currentIndexChanged.connect(self.timestamp_changed)
        top_bar.addWidget(self.combo_timestamp)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Image display area
        self.image_label = ClickableLabel("Please Select Folder First")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #f3f0df; border: 2px dashed #005088;"
            "font-size: 20px; color: #005088;"
        )
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self.image_label.set_callbacks(
            self._on_mouse_press,
            self._on_mouse_move,
            self._on_mouse_release,
        )
        main_layout.addWidget(self.image_label, stretch=4)

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        self.lbl_frame = QLabel("Frame: —")
        self.lbl_frame.setStyleSheet("font-size: 13px; color: #333;")
        bottom_bar.addWidget(self.lbl_frame)
        bottom_bar.addSpacing(30)
        bottom_bar.addWidget(QLabel("Go to Frame:"))

        self.input_frame = QLineEdit()
        self.input_frame.setPlaceholderText("Enter num...")
        self.input_frame.setFixedWidth(100)
        self.input_frame.setStyleSheet("padding: 3px; font-size: 13px;")

        self.int_validator = QIntValidator(0, 999999)
        self.input_frame.setValidator(self.int_validator)
        self.input_frame.returnPressed.connect(self.jump_to_frame)
        bottom_bar.addWidget(self.input_frame)
        bottom_bar.addStretch()

        self.lbl_hint = QLabel(
            "Click: select | Drag: move | Left/Right: rotate 1 degree | Shift+Left/Right: 5 degrees | Ctrl+S: Save"
        )
        self.lbl_hint.setStyleSheet("font-size: 11px; color: #888;")
        bottom_bar.addSpacing(20)
        bottom_bar.addWidget(self.lbl_hint)

        main_layout.addLayout(bottom_bar)

        # Time Slider
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.valueChanged.connect(self.slider_changed)
        main_layout.addWidget(self.time_slider, stretch=1)

    # ---Mouse event handlers---
    def _on_mouse_press(self, dx, dy):
        ix, iy = utils.display_to_image(dx, dy, self.display_offset, self.display_scale)
        hit = utils.hit_test(ix, iy, self.cow_boxes)
        self.selected_cow_idx = hit

        if hit >= 0:
            self.drag_start_img = QPointF(ix, iy)
            self.drag_start_points = [list(p) for p in self.cow_boxes[hit]["points"]]
            self.is_dragging = True
            self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self.is_dragging = False

        self.render_frame()

    def _on_mouse_move(self, dx, dy, is_pressed):
        ix, iy = utils.display_to_image(dx, dy, self.display_offset, self.display_scale)

        if self.is_dragging and is_pressed and self.selected_cow_idx >= 0:
            # Translate selected box relative to drag start
            ddx = ix - self.drag_start_img.x()
            ddy = iy - self.drag_start_img.y()

            # Check if actual translation happened to set dirty state
            if ddx != 0 or ddy != 0:
                self.cow_boxes[self.selected_cow_idx]["points"] = [
                    [p[0] + ddx, p[1] + ddy] for p in self.drag_start_points
                ]
                if not self.has_unsaved_changes:
                    self.has_unsaved_changes = True

            self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.render_frame()
        else:
            # Hover cursor update
            hit = utils.hit_test(ix, iy, self.cow_boxes)
            if hit < 0:
                self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
            elif hit == self.selected_cow_idx:
                self.image_label.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_mouse_release(self):
        self.is_dragging = False
        self.drag_start_img = None
        self.drag_start_points = None
        self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    # ---Keyboard: arrow key rotation & Ctrl+S saving---
    def keyPressEvent(self, event):
        # Handle Ctrl+S saving
        if (
            event.key() == Qt.Key.Key_S
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.save_current_frame()
            return

        if self.selected_cow_idx < 0:
            super().keyPressEvent(event)
            return

        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        angle = 5.0 if shift else 1.0

        if event.key() == Qt.Key.Key_Left:
            self.cow_boxes[self.selected_cow_idx]["points"] = utils.rotate_points(
                self.cow_boxes[self.selected_cow_idx]["points"], -angle
            )
            self.has_unsaved_changes = True
            self.render_frame()
        elif event.key() == Qt.Key.Key_Right:
            self.cow_boxes[self.selected_cow_idx]["points"] = utils.rotate_points(
                self.cow_boxes[self.selected_cow_idx]["points"], angle
            )
            self.has_unsaved_changes = True
            self.render_frame()
        else:
            super().keyPressEvent(event)

    # ---Save handler---
    def save_current_frame(self):
        if not self.has_unsaved_changes or self.current_index >= len(
            self.current_frames
        ):
            return

        frame_data = self.current_frames[self.current_index]
        json_path = frame_data["json_path"]

        if not json_path or not os.path.exists(json_path):
            QMessageBox.warning(
                self, "Save Failed", "No JSON annotation file exists for this frame."
            )
            return

        success = utils.save_cow_json(json_path, self.cow_boxes)
        if success:
            self.has_unsaved_changes = False
            self.render_frame()
        else:
            QMessageBox.critical(
                self, "Save Failed", "Could not write changes back to the JSON file."
            )

    def closeEvent(self, event):
        if self.maybe_save_changes():
            event.accept()
        else:
            event.ignore()

    def maybe_save_changes(self) -> bool:
        if not self.has_unsaved_changes:
            return True

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes in this frame. Would you like to save them?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if reply == QMessageBox.StandardButton.Save:
            self.save_current_frame()
            return not self.has_unsaved_changes
        elif reply == QMessageBox.StandardButton.Discard:
            self.has_unsaved_changes = False
            return True
        else:
            # Cancel
            return False

    # ---Rendering---
    def render_frame(self):
        if self.original_pixmap is None:
            return

        pixmap = self.original_pixmap.copy()
        painter = QPainter(pixmap)

        pen_normal = QPen(QColor(0, 255, 0))
        pen_normal.setWidth(4)
        pen_selected = QPen(QColor(220, 30, 30))
        pen_selected.setWidth(5)
        font_text = QFont("Arial", 16, QFont.Weight.Bold)

        for i, cow in enumerate(self.cow_boxes):
            pts = cow["points"]
            if len(pts) != 4:
                continue

            polygon = utils.polygon_from_points(pts)
            painter.setPen(pen_selected if i == self.selected_cow_idx else pen_normal)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(polygon)

            # ID label
            painter.setPen(QColor(255, 255, 0))
            painter.setFont(font_text)
            painter.drawText(int(pts[0][0]), int(pts[0][1]) - 10, f"ID: {cow['id']}")

        painter.end()

        # Compute scale and offset
        label_w = self.image_label.width()
        label_h = self.image_label.height()
        img_w = pixmap.width()
        img_h = pixmap.height()

        if img_w > 0 and img_h > 0:
            scale = min(label_w / img_w, label_h / img_h)
            scaled_w = img_w * scale
            scaled_h = img_h * scale
            self.display_scale = 1.0 / scale
            self.display_offset = QPointF(
                (label_w - scaled_w) / 2,
                (label_h - scaled_h) / 2,
            )

        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

        # Update title with unsaved changes flag '*'
        selected_timestamp = self.combo_timestamp.currentText()
        real_frame = self.current_frames[self.current_index]["frame_number"]
        unsaved_flag = "*" if self.has_unsaved_changes else ""
        self.setWindowTitle(
            f"Cattle Tracklet Merge Assistant{unsaved_flag} - [{selected_timestamp}]"
            f" - Frame: {real_frame} ({self.current_index}/{self.time_slider.maximum()})"
        )

    # ---Data loading---
    def select_folder(self):
        if not self.maybe_save_changes():
            return

        folder_path = QFileDialog.getExistingDirectory(self, "Open")

        if folder_path:
            self.base_folder_path = Path(folder_path)
            self.temp_json_dir = self.base_folder_path / "temp_json_extracted"

            # extract JSON from zip
            zip_files = list(self.base_folder_path.glob("*json.zip"))
            if zip_files:
                if not self.temp_json_dir.exists() or not any(
                    self.temp_json_dir.iterdir()
                ):
                    with zipfile.ZipFile(zip_files[0], "r") as zip_ref:
                        zip_ref.extractall(self.temp_json_dir)

            frames_dir = self.base_folder_path / "frames"
            if not frames_dir.exists():
                return

            sequence_folders = sorted(
                [d.name for d in frames_dir.iterdir() if d.is_dir()]
            )

            self.combo_timestamp.blockSignals(True)
            self.combo_timestamp.clear()
            self.combo_timestamp.addItems(sequence_folders)
            self.combo_timestamp.blockSignals(False)

            if sequence_folders:
                self.combo_timestamp.setCurrentIndex(0)  # default to first timestamp
                self.timestamp_changed(0)

    def timestamp_changed(self, index):
        if index >= 0 and self.combo_timestamp.signalsBlocked():
            pass
        elif not self.maybe_save_changes():
            return

        selected_timestamp = self.combo_timestamp.currentText()
        if not selected_timestamp or not self.base_folder_path:
            return

        seq_path = self.base_folder_path / "frames" / selected_timestamp

        # Load corresponding JSON paths
        json_files = []
        if self.temp_json_dir and self.temp_json_dir.exists():
            json_files = list(self.temp_json_dir.rglob(f"*{selected_timestamp}*.json"))

        json_dict = {}
        for j in json_files:
            match = re.search(r"frame_(\d+)", j.stem)
            if match:
                json_dict[int(match.group(1))] = str(j)

        # Pair with images
        self.current_frames = []
        img_paths = sorted(list(seq_path.glob("*.jpg")))
        for jpg_path in img_paths:
            match = re.search(r"frame_(\d+)", jpg_path.stem)
            if match:
                frame_no = int(match.group(1))
                self.current_frames.append(
                    {
                        "frame_name": jpg_path.stem,
                        "image_path": str(jpg_path),
                        "json_path": json_dict.get(frame_no, ""),
                        "frame_number": frame_no,
                    }
                )

        total_frames = len(self.current_frames)
        if total_frames > 0:
            max_frame = max(f["frame_number"] for f in self.current_frames)
            self.int_validator.setTop(max_frame)
            self.time_slider.setMaximum(total_frames - 1)
            self.time_slider.setValue(0)
            self.slider_changed(0)

    def parse_cow_json(self, json_path):
        cow_boxes = []
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for shape in data.get("shapes", []):
                if shape.get("label") == "cow":
                    cow_boxes.append(
                        {
                            "id": shape.get("group_id", "Unknown"),
                            "points": [list(p) for p in shape.get("points", [])],
                        }
                    )
        except Exception as e:
            print(f"Error parsing JSON: {e}")

        return cow_boxes

    def slider_changed(self, value):
        if self.has_unsaved_changes:
            self.time_slider.blockSignals(True)
            accepted = self.maybe_save_changes()
            self.time_slider.blockSignals(False)
            if not accepted:
                # Restore previous slider value
                self.time_slider.blockSignals(True)
                self.time_slider.setValue(self.current_index)
                self.time_slider.blockSignals(False)
                return

        if not (self.current_frames and value < len(self.current_frames)):
            return

        self.current_index = value
        frame_data = self.current_frames[value]
        img_path = frame_data["image_path"]
        json_path = frame_data["json_path"]

        real_frame = frame_data["frame_number"]
        self.lbl_frame.setText(f"Frame: {real_frame}")

        if os.path.exists(img_path):
            self.original_pixmap = QPixmap(img_path)

            # Load and store editable cow boxes
            if json_path and os.path.exists(json_path):
                self.cow_boxes = self.parse_cow_json(json_path)
            else:
                self.cow_boxes = []

            # Reset selection on frame change
            self.selected_cow_idx = -1
            self.is_dragging = False
            self.has_unsaved_changes = False

            self.render_frame()

    def jump_to_frame(self):
        target_str = self.input_frame.text()
        if not target_str or not self.current_frames:
            return

        target_frame = int(target_str)

        # search for the target frame in current_frames
        for idx, frame_data in enumerate(self.current_frames):
            if frame_data["frame_number"] == target_frame:
                self.time_slider.setValue(idx)
                self.input_frame.clear()
                return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CowTrackerApp()
    window.show()
    sys.exit(app.exec())
