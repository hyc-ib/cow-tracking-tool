"""
Cattle Tracklet Merge Assistant (Frame Edition)

Folder structure expected:
  image_all/
    └── <128>/
        └── <20250910T054822_20250910T060922>/
            └── <20250910T054822_20250910T060922_frame_1350>.jpg
            └── <20250910T054822_20250910T060922_frame_4125>.jpg
        └── <20250910T060922_20250910T063022>/
            └── <20250910T060922_20250910T063022_frame_0475>.jpg
            └── <20250910T060922_20250910T063022_frame_1000>.jpg
    └── <133>/
        └── <20250910T060058_20250910T062151>/
            └── <20250910T060058_20250910T062151_frame_0125>.jpg
            └── <20250910T060058_20250910T062151_frame_0275>.jpg
        └── <20250910T100443_20250910T102601>/
            └── <20250910T100443_20250910T102601_frame_0650>.jpg
            └── <20250910T100443_20250910T102601_frame_0950>.jpg

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
"""

import json
import os
import re
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QIntValidator, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

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


class AnomalySlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.anomaly_indices = []  # list of slider indices (0 to max)

    def set_anomalies(self, indices):
        self.anomaly_indices = indices
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.anomaly_indices or self.maximum() <= 0:
            return

        painter = QPainter(self)
        painter.setPen(QPen(QColor(255, 0, 0, 200), 2))

        margin = 6
        width = self.width() - 2 * margin
        height = self.height()

        for idx in self.anomaly_indices:
            ratio = idx / self.maximum()
            x = margin + int(ratio * width)
            painter.drawLine(x, 2, x, height // 2 - 2)

        painter.end()


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_frames = []
        self.json_session_dir = None  # path to the selected JSON session folder
        self._session_name = ""
        self._image_root_dir: Path | None = None
        self._json_root_dir: Path | None = None

        # Edit mode state
        self.cow_boxes = []
        self.selected_cow_idx = -1  # nothing selected
        self.drag_start_img = None
        self.drag_start_points = None
        self.is_dragging = False
        self.drag_happened = False
        self.current_idx = 0
        self.pending_cow_id = None

        # Draw mode state
        self.draw_mode = False
        self.draw_start_img = None
        self.draw_preview_pts = None

        # Display state
        self.original_pixmap = None
        self.display_scale = 1.0  # image_pixels / display_pixel
        self.display_offset = QPointF(0, 0)

        # Anomaly state
        self.current_anomalies = {}  # {frame_number: description}

        self.setWindowTitle("Cattle Tracklet Merge Assistant - Frame Edition")
        self.setMinimumSize(900, 600)

        # Widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top Bar
        top_bar = QHBoxLayout()
        self.btn_set_img_root = QPushButton("Image Folder")
        self.btn_set_img_root.setStyleSheet(
            "font-size: 12px; padding: 6px 12px; background-color: #005088; color: white; border-radius: 4px;"
        )
        self.btn_set_img_root.clicked.connect(self.set_image_root)
        top_bar.addWidget(self.btn_set_img_root)

        self.btn_set_json_root = QPushButton("JSON Folder")
        self.btn_set_json_root.setStyleSheet(
            "font-size: 12px; padding: 6px 12px; background-color: #005088; color: white; border-radius: 4px;"
        )
        self.btn_set_json_root.clicked.connect(self.set_json_root)
        top_bar.addWidget(self.btn_set_json_root)

        top_bar.addWidget(QLabel("Camera:"))
        self.combo_camera = QComboBox()
        self.combo_camera.setMinimumWidth(80)
        self.combo_camera.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_camera.currentIndexChanged.connect(self.camera_changed)
        top_bar.addWidget(self.combo_camera)

        top_bar.addWidget(QLabel("Session:"))
        self.combo_session = QComboBox()
        self.combo_session.setMinimumWidth(250)
        self.combo_session.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_session.currentIndexChanged.connect(self.session_changed)
        top_bar.addWidget(self.combo_session)

        self.lbl_session_info = QLabel("")
        self.lbl_session_info.setStyleSheet(
            "font-size: 11px; color: #888; font-style: italic;"
        )
        top_bar.addWidget(self.lbl_session_info)

        # Vertical separator
        top_sep = QFrame()
        top_sep.setFrameShape(QFrame.Shape.VLine)
        top_sep.setStyleSheet("color: #ccc;")
        top_bar.addSpacing(8)
        top_bar.addWidget(top_sep)
        top_bar.addSpacing(8)

        self.btn_draw = QPushButton("New Box [N]")
        self.btn_draw.setCheckable(True)
        self.btn_draw.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_draw.setStyleSheet(
            "QPushButton { font-size: 13px; padding: 6px 14px; border-radius: 4px;"
            " background-color: #005088; color: white; }"
            "QPushButton:checked { background-color: #c06000; }"
        )
        self.btn_draw.clicked.connect(self.toggle_draw_mode)
        top_bar.addWidget(self.btn_draw)

        top_bar.addSpacing(6)
        self.btn_delete = QPushButton("Delete [Del]")
        self.btn_delete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_delete.setStyleSheet(
            "font-size: 13px; padding: 6px 14px; border-radius: 4px;"
            " background-color: #aa0000; color: white;"
        )
        self.btn_delete.clicked.connect(self.delete_selected_box)
        top_bar.addWidget(self.btn_delete)

        top_bar.addSpacing(12)
        self.lbl_tool_status = QLabel("")
        self.lbl_tool_status.setStyleSheet("font-size: 11px; color: #666;")
        top_bar.addWidget(self.lbl_tool_status)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Anomaly info bar — full-width row below top bar
        anomaly_bar = QHBoxLayout()
        anomaly_bar.setContentsMargins(4, 0, 4, 2)
        self.lbl_anomaly_info = QLabel("")
        self.lbl_anomaly_info.setStyleSheet(
            "font-size: 12px; color: #d00000; font-weight: bold;"
        )
        anomaly_bar.addWidget(self.lbl_anomaly_info, stretch=1)
        main_layout.addLayout(anomaly_bar)

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

        # Coat Pattern Viewer Panel
        self.strip_container = QFrame()
        self.strip_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.strip_container.setStyleSheet(
            "QFrame { background-color: #1e1e24; border-radius: 6px; border: 1px solid #2d2d3a; }"
        )
        strip_vbox = QVBoxLayout(self.strip_container)
        strip_vbox.setContentsMargins(10, 6, 10, 6)
        strip_vbox.setSpacing(4)

        # Header
        self.lbl_strip_header = QLabel(
            "Coat Pattern Viewer — Select a cow box to inspect sequence"
        )
        self.lbl_strip_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_strip_header.setStyleSheet(
            "color: #b0b0ba; font-size: 12px; font-weight: bold;"
        )
        strip_vbox.addWidget(self.lbl_strip_header)

        # Scroll Area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(95)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.strip_layout = QHBoxLayout(scroll_content)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(8)

        scroll_area.setWidget(scroll_content)
        strip_vbox.addWidget(scroll_area)

        # Add placeholder card UI widgets
        self.strip_card_widgets = []
        self._init_strip_placeholders()

        main_layout.addWidget(self.strip_container, stretch=0)

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        self.lbl_frame = QLabel("Frame: —")
        self.lbl_frame.setStyleSheet("font-size: 13px; color: #333;")
        bottom_bar.addWidget(self.lbl_frame)
        bottom_bar.addSpacing(15)

        self.btn_next_issue = QPushButton("Next Issue [F]")
        self.btn_next_issue.setStyleSheet(
            "font-size: 12px; padding: 4px 10px; background-color: #d00000; color: white; border-radius: 4px;"
        )
        self.btn_next_issue.clicked.connect(self.jump_to_next_issue)
        bottom_bar.addWidget(self.btn_next_issue)

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
            "A/D: Prev/Next Frame | Click: Select | Drag: Move | Left/Right: Rotate 1 degree | Shift+Left/Right: Rotate 5 degrees"
        )
        self.lbl_hint.setStyleSheet("font-size: 11px; color: #888;")
        bottom_bar.addSpacing(20)
        bottom_bar.addWidget(self.lbl_hint)

        main_layout.addLayout(bottom_bar)

        # Time Slider
        self.time_slider = AnomalySlider(Qt.Orientation.Horizontal)
        self.time_slider.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )  # Prevent grabbing keyboard focus and intercepting arrows
        self.time_slider.valueChanged.connect(self.slider_changed)
        main_layout.addWidget(self.time_slider, stretch=1)

        # Set main window focus policy
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    # ---Mouse event handlers---
    def _on_mouse_press(self, dx, dy):
        self.setFocus()
        ix, iy = utils.display_to_image(dx, dy, self.display_offset, self.display_scale)

        if self.draw_mode:
            self.draw_start_img = (ix, iy)
            return

        hit = utils.hit_test(ix, iy, self.cow_boxes)
        self.selected_cow_idx = hit

        if hit >= 0:
            self.drag_start_img = QPointF(ix, iy)
            self.drag_start_points = [list(p) for p in self.cow_boxes[hit]["points"]]
            self.is_dragging = True
            self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self.is_dragging = False

        self._update_strip_header()
        self._render_frame()

    def _on_mouse_move(self, dx, dy, is_pressed):
        ix, iy = utils.display_to_image(dx, dy, self.display_offset, self.display_scale)

        if self.draw_mode:
            self.image_label.setCursor(Qt.CursorShape.CrossCursor)
            if is_pressed and self.draw_start_img is not None:
                x0, y0 = self.draw_start_img
                self.draw_preview_pts = [[x0, y0], [ix, y0], [ix, iy], [x0, iy]]
                self._render_frame()
            return

        if self.is_dragging and is_pressed and self.selected_cow_idx >= 0:
            # Translate selected box relative to drag start
            ddx = ix - self.drag_start_img.x()
            ddy = iy - self.drag_start_img.y()

            if ddx != 0 or ddy != 0:
                self.cow_boxes[self.selected_cow_idx]["points"] = [
                    [p[0] + ddx, p[1] + ddy] for p in self.drag_start_points
                ]
                self.drag_happened = True

            self.image_label.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._update_strip_header()
            self._render_frame()
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
        if self.draw_mode:
            if self.draw_start_img is not None and self.draw_preview_pts is not None:
                cow_id = self.pending_cow_id
                self.cow_boxes.append({"id": cow_id, "points": self.draw_preview_pts})
                self._save_current_frame()
                self.lbl_tool_status.setText(f"\u2713 Added ID {cow_id}")
            self._exit_draw_mode()  # clears preview, pending_cow_id, and re-renders
            return

        self.is_dragging = False
        self.drag_start_img = None
        self.drag_start_points = None
        self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
        if self.drag_happened:
            self.drag_happened = False
            self._save_current_frame()

    # ---Keyboard shortcuts---
    def keyPressEvent(self, event):
        # N: Draw new box
        if event.key() == Qt.Key.Key_N:
            self.toggle_draw_mode()
            return

        # Del: Remove selected box
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_box()
            return

        # A: Previous Frame
        if event.key() == Qt.Key.Key_A:
            if self.current_idx > 0:
                self.time_slider.setValue(self.current_idx - 1)
            return

        # D: Next Frame
        if event.key() == Qt.Key.Key_D:
            if self.current_idx < len(self.current_frames) - 1:
                self.time_slider.setValue(self.current_idx + 1)
            return

        # F: Jump to next issue
        if event.key() == Qt.Key.Key_F:
            self.jump_to_next_issue()
            return

        if self.selected_cow_idx < 0:
            super().keyPressEvent(event)
            return

        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        angle = 5.0 if shift else 1.0

        if key == Qt.Key.Key_Left:
            self.cow_boxes[self.selected_cow_idx]["points"] = utils.rotate_points(
                self.cow_boxes[self.selected_cow_idx]["points"], -angle
            )
            self._render_frame()
            self._save_current_frame()
            self._update_strip_header()
        elif key == Qt.Key.Key_Right:
            self.cow_boxes[self.selected_cow_idx]["points"] = utils.rotate_points(
                self.cow_boxes[self.selected_cow_idx]["points"], angle
            )
            self._render_frame()
            self._save_current_frame()
            self._update_strip_header()
        else:
            super().keyPressEvent(event)

    # ---Draw mode helpers---
    def toggle_draw_mode(self):
        if self.draw_mode:
            self._exit_draw_mode()
            return

        cow_id_text, ok = QInputDialog.getText(
            self, "New Bounding Box", "Enter Cow ID:"
        )
        if not ok or not cow_id_text.strip():
            self.btn_draw.setChecked(False)
            return

        raw = cow_id_text.strip()
        try:
            self.pending_cow_id = int(raw)
        except ValueError:
            self.pending_cow_id = raw

        self.draw_mode = True
        self.draw_preview_pts = None
        self.draw_start_img = None
        self.selected_cow_idx = -1
        self.image_label.setCursor(Qt.CursorShape.CrossCursor)
        self.btn_draw.setChecked(True)
        self.lbl_tool_status.setText(
            f"Drawing ID {self.pending_cow_id} — drag to place box"
        )
        self._update_strip_header()
        self._render_frame()

    def _exit_draw_mode(self):
        self.draw_mode = False
        self.draw_preview_pts = None
        self.draw_start_img = None
        self.pending_cow_id = None
        self.image_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.btn_draw.setChecked(False)
        self._update_strip_header()
        self._render_frame()

    def delete_selected_box(self):
        if self.selected_cow_idx < 0 or self.selected_cow_idx >= len(self.cow_boxes):
            return
        self.cow_boxes.pop(self.selected_cow_idx)
        self.selected_cow_idx = -1
        self._save_current_frame()
        self._update_strip_header()
        self._render_frame()

    # ---Save handler---
    def _save_current_frame(self):
        if self.current_idx >= len(self.current_frames):
            return

        frame_data = self.current_frames[self.current_idx]
        json_path = frame_data["json_path"]

        # Create a skeleton JSON file if it doesn't exist
        if not json_path or not os.path.exists(json_path):
            json_path = self._create_json_for_frame(frame_data)
            if not json_path:
                return
            self.current_frames[self.current_idx]["json_path"] = json_path

        success = utils.save_cow_json(json_path, self.cow_boxes)
        if not success:
            QMessageBox.critical(
                self, "Save Failed", "Could not write changes back to the JSON file."
            )

    def _create_json_for_frame(self, frame_data: dict) -> str:
        if not self.json_session_dir:
            QMessageBox.warning(self, "Save Failed", "No annotation directory is set.")
            return ""

        self.json_session_dir.mkdir(parents=True, exist_ok=True)

        img_basename = os.path.basename(frame_data["image_path"])
        json_stem = os.path.splitext(img_basename)[0]  # strip .jpg
        json_path = str(self.json_session_dir / f"{json_stem}.json")

        img_w = self.original_pixmap.width() if self.original_pixmap else 0
        img_h = self.original_pixmap.height() if self.original_pixmap else 0

        skeleton = {
            "version": "5.0.0",
            "flags": {},
            "shapes": [],
            "imagePath": img_basename,
            "imageData": None,
            "imageHeight": img_h,
            "imageWidth": img_w,
        }

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(skeleton, f, indent=2, ensure_ascii=False)
            return json_path
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", f"Could not create JSON: {e}")
            return ""

    # ---Rendering---
    def _render_frame(self):
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

        # Draw preview rectangle (draw mode)
        if self.draw_preview_pts and len(self.draw_preview_pts) == 4:
            pen_preview = QPen(QColor(0, 120, 255))
            pen_preview.setWidth(2)
            pen_preview.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen_preview)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(utils.polygon_from_points(self.draw_preview_pts))

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

        # Update window title
        real_frame = self.current_frames[self.current_idx]["frame_number"]
        self.setWindowTitle(
            f"Cattle Tracklet Merge Assistant - [{self._session_name}]"
            f" - Frame: {real_frame} ({self.current_idx}/{self.time_slider.maximum()})"
        )

    # ---Data loading---
    def set_image_root(self):
        start_dir = str(self._image_root_dir) if self._image_root_dir else ""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Image Root Folder (e.g. image_all)", start_dir
        )
        if folder:
            self._image_root_dir = Path(folder)
            self.btn_set_img_root.setText("Image Folder")
            self.update_camera_dropdown()

    def set_json_root(self):
        start_dir = str(self._json_root_dir) if self._json_root_dir else ""
        folder = QFileDialog.getExistingDirectory(
            self, "Select JSON Root Folder (e.g. json)", start_dir
        )
        if folder:
            self._json_root_dir = Path(folder)
            self.btn_set_json_root.setText("JSON Folder")
            self.update_camera_dropdown()

    def update_camera_dropdown(self):
        self.combo_camera.blockSignals(True)
        self.combo_camera.clear()
        if self._image_root_dir and self._image_root_dir.exists():
            cams = sorted(
                [d.name for d in self._image_root_dir.iterdir() if d.is_dir()]
            )
            self.combo_camera.addItems(cams)
        self.combo_camera.blockSignals(False)
        if self.combo_camera.count() > 0:
            self.combo_camera.setCurrentIndex(0)
            self.camera_changed()

    def camera_changed(self, index=0):
        self.combo_session.blockSignals(True)
        self.combo_session.clear()
        cam_id = self.combo_camera.currentText()
        if cam_id and self._image_root_dir:
            cam_dir = self._image_root_dir / cam_id
            if cam_dir.exists():
                sessions = sorted([d.name for d in cam_dir.iterdir() if d.is_dir()])
                self.combo_session.addItems(sessions)
        self.combo_session.blockSignals(False)
        if self.combo_session.count() > 0:
            self.combo_session.setCurrentIndex(0)
            self.session_changed()

    def session_changed(self, index=0):
        cam_id = self.combo_camera.currentText()
        session_id = self.combo_session.currentText()
        if (
            not cam_id
            or not session_id
            or not self._image_root_dir
            or not self._json_root_dir
        ):
            self.lbl_session_info.setText("")
            return

        img_dir = self._image_root_dir / cam_id / session_id

        # Find matching json camera dir (e.g. 128camera_json matches 128)
        json_cam_dir = None
        for d in self._json_root_dir.iterdir():
            if d.is_dir():
                if (
                    d.name == cam_id
                    or d.name == f"{cam_id}camera_json"
                    or d.name == f"{cam_id}camera"
                ):
                    json_cam_dir = d
                    break

        if not json_cam_dir:
            self.lbl_session_info.setText(
                f"JSON folder for camera {cam_id} not found! Check naming."
            )
            return

        json_dir = json_cam_dir / session_id
        if not json_dir.exists():
            self.lbl_session_info.setText(
                f"JSON session folder missing: {json_dir.name}"
            )
            # We still load the images, but with no JSONs
            self._load_session(img_dir, json_dir, {})
            return

        # Parse anomalies.json here, where json_cam_dir and session_id are in scope
        anomalies: dict = {}
        anomaly_path = self._json_root_dir / "anomalies.json"
        if anomaly_path.exists():
            try:
                with open(anomaly_path, "r", encoding="utf-8") as f:
                    anomaly_data = json.load(f)
                cam_entry = anomaly_data.get("cameras", {}).get(json_cam_dir.name, {})
                session_entries = cam_entry.get(session_id, {}).get("anomalies", [])
                for a in session_entries:
                    frame = a.get("frame")
                    if frame is not None:
                        atype = a.get("type", "UNKNOWN")
                        desc = a.get("description", "")
                        msg = f"\u26a0\ufe0f {atype}: {desc}"
                        if frame not in anomalies:
                            anomalies[frame] = []
                        anomalies[frame].append(msg)
            except Exception as e:
                print(f"Error parsing anomalies.json: {e}")

        self._load_session(img_dir, json_dir, anomalies)

    def _load_session(self, img_dir: Path, json_dir: Path, anomalies: dict = None):
        """Pair image and JSON files by frame number, then load the first frame."""
        self.json_session_dir = json_dir
        self._session_name = img_dir.name
        self.current_anomalies = anomalies or {}

        # Build JSON index: {frame_no: json_path_str}
        json_dict: dict = {}
        for json_path in json_dir.glob("*.json"):
            m = re.search(r"frame_(\d+)", json_path.stem)
            if m:
                json_dict[int(m.group(1))] = str(json_path)

        # Pair every JPG with its JSON (empty string if no annotation yet)
        self.current_frames = []
        for jpg_path in sorted(img_dir.glob("*.jpg")):
            m = re.search(r"frame_(\d+)", jpg_path.stem)
            if m:
                frame_no = int(m.group(1))
                self.current_frames.append(
                    {
                        "image_path": str(jpg_path),
                        "json_path": json_dict.get(frame_no, ""),
                        "frame_number": frame_no,
                    }
                )

        self.current_frames.sort(key=lambda x: x["frame_number"])

        total = len(self.current_frames)
        if total == 0:
            self.lbl_session_info.setText("No frames found in the selected folder.")
            return

        max_frame = max(f["frame_number"] for f in self.current_frames)
        self.int_validator.setTop(max_frame)
        self.time_slider.setMaximum(total - 1)

        # Mark anomalies on the slider
        anomaly_indices = []
        for i, frame_data in enumerate(self.current_frames):
            if frame_data["frame_number"] in self.current_anomalies:
                anomaly_indices.append(i)
        self.time_slider.set_anomalies(anomaly_indices)

        self.time_slider.setValue(0)
        self.slider_changed(0)

        # Update session info with anomaly count
        n_issues = len(self.current_anomalies)
        if n_issues > 0:
            self.lbl_session_info.setText(
                f"{total} frames  \u00b7  \u26a0\ufe0f {n_issues} issue frames detected"
            )
        else:
            self.lbl_session_info.setText(f"{total} frames  \u00b7  \u2705 No issues")

    def _parse_cow_json(self, json_path):
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
        if not (self.current_frames and value < len(self.current_frames)):
            return

        self.current_idx = value
        frame_data = self.current_frames[value]
        img_path = frame_data["image_path"]
        json_path = frame_data["json_path"]

        real_frame = frame_data["frame_number"]
        self.lbl_frame.setText(f"Frame: {real_frame}")

        # Show anomaly info if present (join multiple anomalies on same frame)
        if real_frame in self.current_anomalies:
            msgs = self.current_anomalies[real_frame]
            self.lbl_anomaly_info.setText("  \u2502  ".join(msgs))
        else:
            self.lbl_anomaly_info.setText("")

        if os.path.exists(img_path):
            self.original_pixmap = QPixmap(img_path)

            # Load and store editable cow boxes
            if json_path and os.path.exists(json_path):
                self.cow_boxes = self._parse_cow_json(json_path)
            else:
                self.cow_boxes = []

            # Reset selection and status on frame change
            self.selected_cow_idx = -1
            self.is_dragging = False
            self.drag_happened = False
            self.lbl_tool_status.setText("")

            self._update_strip_header()
            self._render_frame()

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
            self.input_frame.clearFocus()

    def jump_to_next_issue(self):
        if not self.current_frames or not self.current_anomalies:
            self.lbl_anomaly_info.setText("✅ No issues found in this session.")
            return

        current_idx = self.time_slider.value()

        # Find the next index that has an anomaly
        for i in range(current_idx + 1, len(self.current_frames)):
            frame_no = self.current_frames[i]["frame_number"]
            if frame_no in self.current_anomalies:
                self.time_slider.setValue(i)
                return

        # If we reached the end, check if we want to wrap around or just show a message
        self.lbl_anomaly_info.setText("✅ You've reached the last issue.")

    # ---Strip Viewer UI Helpers---
    def _init_strip_placeholders(self):
        offsets = [-3, -2, -1, 0, 1, 2, 3]
        for offset in offsets:
            card = QFrame()
            card.setFixedSize(110, 72)
            card.setStyleSheet(
                "QFrame { background-color: #2b2b36; border: 1px solid #3d3d4d; border-radius: 4px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(4, 2, 4, 2)
            card_layout.setSpacing(2)

            offset_text = "Current" if offset == 0 else f"{offset:+d}f"
            lbl_offset = QLabel(offset_text)
            lbl_offset.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_offset.setStyleSheet(
                "color: #00d084; font-size: 10px; font-weight: bold;"
                if offset == 0
                else "color: #8a8a9e; font-size: 10px; font-weight: bold;"
            )
            card_layout.addWidget(lbl_offset)

            lbl_img = QLabel("No Data")
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_img.setStyleSheet("color: #555566; font-size: 11px;")
            card_layout.addWidget(lbl_img, stretch=1)

            if offset != 0:
                card.setCursor(Qt.CursorShape.PointingHandCursor)

                def make_click_handler(o):
                    def handler(event):
                        if event.button() == Qt.MouseButton.LeftButton:
                            self._jump_to_offset(o)
                    return handler

                card.mousePressEvent = make_click_handler(offset)

            self.strip_layout.addWidget(card)
            self.strip_card_widgets.append(
                {
                    "container": card,
                    "offset_lbl": lbl_offset,
                    "img_lbl": lbl_img,
                    "offset": offset,
                }
            )

        self.strip_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _jump_to_offset(self, offset: int):
        """Jump the time slider by `offset` steps relative to the current frame."""
        target = self.current_idx + offset
        target = max(0, min(target, len(self.current_frames) - 1))
        self.time_slider.setValue(target)

    def _update_strip_header(self):
        if 0 <= self.selected_cow_idx < len(self.cow_boxes):
            cow_id = self.cow_boxes[self.selected_cow_idx]["id"]
            self.lbl_strip_header.setText(f"Coat Pattern Viewer — Cow ID: {cow_id}")
            self.lbl_strip_header.setStyleSheet(
                "color: #00d084; font-size: 12px; font-weight: bold;"
            )
        else:
            self.lbl_strip_header.setText(
                "Coat Pattern Viewer — Select a cow box to inspect sequence"
            )
            self.lbl_strip_header.setStyleSheet(
                "color: #b0b0ba; font-size: 12px; font-weight: bold;"
            )

        self._update_strip_viewer_content()

    def _update_strip_viewer_content(self):
        offsets = [-3, -2, -1, 0, 1, 2, 3]

        if not (0 <= self.selected_cow_idx < len(self.cow_boxes)):
            for idx, offset in enumerate(offsets):
                card = self.strip_card_widgets[idx]
                card["img_lbl"].setPixmap(QPixmap())
                card["img_lbl"].setText("No Data")
                card["img_lbl"].setStyleSheet("color: #555566; font-size: 11px;")
                card["container"].setStyleSheet(
                    "QFrame { background-color: #2b2b36; border: 1px solid #3d3d4d; border-radius: 4px; }"
                )
            return

        target_cow_id = str(self.cow_boxes[self.selected_cow_idx]["id"])

        for idx, offset in enumerate(offsets):
            card = self.strip_card_widgets[idx]
            target_frame_idx = self.current_idx + offset

            border_color = "#00d084" if offset == 0 else "#3d3d4d"
            card["container"].setStyleSheet(
                f"QFrame {{ background-color: #2b2b36; border: 1px solid {border_color}; border-radius: 4px; }}"
            )

            if not (0 <= target_frame_idx < len(self.current_frames)):
                card["img_lbl"].setPixmap(QPixmap())
                card["img_lbl"].setText("—")
                card["img_lbl"].setStyleSheet("color: #555566; font-size: 11px;")
                continue

            frame_data = self.current_frames[target_frame_idx]
            img_path = frame_data["image_path"]
            json_path = frame_data["json_path"]

            if offset == 0:
                matching_box = next(
                    (b for b in self.cow_boxes if str(b["id"]) == target_cow_id), None
                )
            else:
                boxes = (
                    self._parse_cow_json(json_path)
                    if json_path and os.path.exists(json_path)
                    else []
                )
                matching_box = next(
                    (b for b in boxes if str(b["id"]) == target_cow_id), None
                )

            if matching_box and os.path.exists(img_path):
                target_pixmap = (
                    self.original_pixmap
                    if (offset == 0 and self.original_pixmap)
                    else QPixmap(img_path)
                )
                crop = utils.crop_and_derotate_bbox(
                    target_pixmap, matching_box["points"]
                )
                if crop and not crop.isNull():
                    scaled_crop = crop.scaled(
                        90,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    card["img_lbl"].setPixmap(scaled_crop)
                    card["img_lbl"].setText("")
                else:
                    card["img_lbl"].setPixmap(QPixmap())
                    card["img_lbl"].setText("Invalid")
                    card["img_lbl"].setStyleSheet("color: #aa5555; font-size: 11px;")
            else:
                card["img_lbl"].setPixmap(QPixmap())
                card["img_lbl"].setText("Missing")
                card["img_lbl"].setStyleSheet("color: #aa7744; font-size: 11px;")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CowTrackerApp()
    window.showMaximized()
    sys.exit(app.exec())
