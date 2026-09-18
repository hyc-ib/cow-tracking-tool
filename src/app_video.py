"""
Cattle Tracklet Merge Assistant (Video Edition)

Folder structure expected:
  videos/
    └── camera<128>_mask/
        ├── <20250910T065927_20250910T072033>.mp4
        └── <20250910T072033_20250910T074139>.mp4
    └── camera<133>_mask/
        └── ...

  json/
    └── <128>camera_json/
        └── <20250910T065927_20250910T072033>/
            └── <20250910T065927_20250910T072033_frame_0050>.json
    └── <133>camera_json/
        └── ...
"""

import re
import sys
import json
from pathlib import Path

import cv2
from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import interpolation_engine

ANNOTATION_FPS = 16.15
SPEED_OPTIONS = [("0.25x", 0.25), ("0.5x", 0.5), ("1x", 1.0), ("2x", 2.0)]


class VideoFrameProvider:
    def __init__(self):
        self.cap = None
        self.total_frames = 0
        self.fps = ANNOTATION_FPS

    def open(self, video_path: str) -> bool:
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            return False
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or ANNOTATION_FPS
        return True

    def get_frame(self, frame_no: int):
        if not self.cap or not self.cap.isOpened():
            return None
        current_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        if frame_no == current_pos:
            pass
        elif frame_no > current_pos and frame_no - current_pos <= 30:
            for _ in range(frame_no - current_pos):
                self.cap.read()
        else:
            seek_target = max(0, frame_no - 30)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, seek_target)
            actual_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            if actual_pos <= frame_no:
                for _ in range(frame_no - actual_pos):
                    self.cap.read()
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = self.cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.video_provider = VideoFrameProvider()
        self.dense_cow_boxes = {}
        self._video_root_dir: Path | None = None
        self._json_root_dir: Path | None = None
        self._playback_speed = 1.0

        self.setWindowTitle("Cattle Tracklet Merge Assistant — Video Edition")
        self.setMinimumSize(900, 600)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top Bar
        top_bar = QHBoxLayout()

        self.btn_set_video_root = QPushButton("Video Folder")
        self.btn_set_video_root.setStyleSheet(
            "font-size: 12px; padding: 6px 12px; background-color: #005088; color: white; border-radius: 4px;"
        )
        self.btn_set_video_root.clicked.connect(self.set_video_root)
        top_bar.addWidget(self.btn_set_video_root)

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

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(
            "font-size: 11px; color: #888; font-style: italic;"
        )
        top_bar.addWidget(self.lbl_status)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Video display
        self.image_label = QLabel("Please select Video Folder and JSON Folder")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #1a1a1a; border: 2px dashed #005088;"
            "font-size: 18px; color: #005088;"
        )
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        main_layout.addWidget(self.image_label, stretch=1)

        # Progress Slider
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.time_slider.valueChanged.connect(self._on_slider_changed)
        main_layout.addWidget(self.time_slider)

        # Player control bar
        ctrl_bar = QHBoxLayout()

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setFixedWidth(44)
        self.btn_prev.setStyleSheet(self._btn_style())
        self.btn_prev.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_prev.clicked.connect(self._prev_frame)
        ctrl_bar.addWidget(self.btn_prev)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedWidth(54)
        self.btn_play.setStyleSheet(self._btn_style(accent=True))
        self.btn_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_play.clicked.connect(self.toggle_playback)
        ctrl_bar.addWidget(self.btn_play)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedWidth(44)
        self.btn_next.setStyleSheet(self._btn_style())
        self.btn_next.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_next.clicked.connect(self._next_frame)
        ctrl_bar.addWidget(self.btn_next)

        ctrl_bar.addSpacing(16)
        ctrl_bar.addWidget(QLabel("Speed:"))

        self.speed_buttons = {}
        for label, factor in SPEED_OPTIONS:
            btn = QPushButton(label)
            btn.setFixedWidth(48)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCheckable(True)
            btn.setChecked(label == "1x")
            btn.clicked.connect(lambda checked, f=factor, b=btn: self._set_speed(f, b))
            btn.setStyleSheet(self._speed_btn_style(active=(label == "1x")))
            self.speed_buttons[label] = btn
            ctrl_bar.addWidget(btn)

        ctrl_bar.addSpacing(16)

        self.lbl_time = QLabel("00:00 / 00:00  (frame 0)")
        self.lbl_time.setStyleSheet("font-size: 12px; color: #555; min-width: 210px;")
        ctrl_bar.addWidget(self.lbl_time)

        ctrl_bar.addStretch()
        main_layout.addLayout(ctrl_bar)

        # Playback timer
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self._advance_frame)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    # Style helpers
    def _btn_style(self, accent=False):
        bg = "#007acc" if accent else "#005088"
        return (
            f"QPushButton {{ font-size: 14px; padding: 5px 8px; background-color: {bg}; "
            f"color: white; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: #0066aa; }}"
        )

    def _speed_btn_style(self, active=False):
        bg = "#c06000" if active else "#3a3a4a"
        return (
            f"QPushButton {{ font-size: 11px; padding: 4px 4px; background-color: {bg}; "
            f"color: white; border-radius: 4px; }}"
        )

    # Root folder selection
    def set_video_root(self):
        start = str(self._video_root_dir) if self._video_root_dir else ""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Video Root Folder (e.g. videos)", start
        )
        if folder:
            self._video_root_dir = Path(folder)
            self._update_camera_dropdown()

    def set_json_root(self):
        start = str(self._json_root_dir) if self._json_root_dir else ""
        folder = QFileDialog.getExistingDirectory(
            self, "Select JSON Root Folder (e.g. json)", start
        )
        if folder:
            self._json_root_dir = Path(folder)

    # Dropdowns
    def _update_camera_dropdown(self):
        self.combo_camera.blockSignals(True)
        self.combo_camera.clear()
        if self._video_root_dir and self._video_root_dir.exists():
            for d in sorted(self._video_root_dir.iterdir()):
                if d.is_dir():
                    m = re.match(r"camera(\d+)_mask", d.name)
                    if m:
                        self.combo_camera.addItem(m.group(1), d)
        self.combo_camera.blockSignals(False)
        if self.combo_camera.count() > 0:
            self.combo_camera.setCurrentIndex(0)
            self.camera_changed()

    def camera_changed(self, index=0):
        self.combo_session.blockSignals(True)
        self.combo_session.clear()
        cam_dir: Path | None = self.combo_camera.currentData()
        if cam_dir and cam_dir.exists():
            for mp4 in sorted(cam_dir.glob("*.mp4")):
                self.combo_session.addItem(mp4.stem, mp4)
        self.combo_session.blockSignals(False)
        if self.combo_session.count() > 0:
            self.combo_session.setCurrentIndex(0)
            self.session_changed()

    def session_changed(self, index=0):
        video_path: Path | None = self.combo_session.currentData()
        cam_id = self.combo_camera.currentText()
        if not video_path or not cam_id:
            return

        self.play_timer.stop()
        self.btn_play.setText("▶")

        if not self.video_provider.open(str(video_path)):
            self.lbl_status.setText(f"Failed to open: {video_path.name}")
            return

        timestamp = video_path.stem
        self.dense_cow_boxes = {}

        if self._json_root_dir and self._json_root_dir.exists():
            json_cam_dir = None
            for d in self._json_root_dir.iterdir():
                if d.is_dir() and (
                    d.name == cam_id
                    or d.name == f"{cam_id}camera_json"
                    or d.name == f"{cam_id}camera"
                ):
                    json_cam_dir = d
                    break

            if json_cam_dir:
                json_session_dir = json_cam_dir / timestamp
                if json_session_dir.exists():
                    json_dict = {}
                    video_fps = self.video_provider.fps
                    for json_path in json_session_dir.glob("*.json"):
                        m = re.search(r"frame_(\d+)", json_path.stem)
                        if m:
                            ann_frame = int(m.group(1))
                            time_sec = ann_frame / ANNOTATION_FPS
                            vid_frame = round(time_sec * video_fps)
                            json_dict[vid_frame] = json_path

                    if json_dict:
                        self.dense_cow_boxes = (
                            interpolation_engine.generate_dense_cache(
                                json_dict,
                                self._parse_cow_json,
                                self.video_provider.total_frames,
                                fps=video_fps,
                            )
                        )
                        self.lbl_status.setText(
                            f"{len(json_dict)} annotated frames  ·  interpolated to {self.video_provider.total_frames:,} frames"
                        )
                    else:
                        self.lbl_status.setText("No matching JSON files found")
                else:
                    self.lbl_status.setText(
                        f"JSON session folder not found: {timestamp}"
                    )
            else:
                self.lbl_status.setText(
                    f"JSON camera folder for camera {cam_id} not found"
                )

        total = self.video_provider.total_frames
        self.time_slider.setMaximum(max(0, total - 1))
        self.time_slider.setValue(0)
        self._on_slider_changed(0)

    # Parsing
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
                            "points": shape.get("points", []),
                        }
                    )
        except Exception as e:
            print(f"Error parsing JSON: {e}")
        return cow_boxes

    # Frame rendering
    def _on_slider_changed(self, video_frame_no: int):
        pixmap = self.video_provider.get_frame(video_frame_no)
        if pixmap is None:
            return

        boxes = self.dense_cow_boxes.get(video_frame_no, [])
        if boxes:
            painter = QPainter(pixmap)
            pen_box = QPen(QColor(0, 255, 0))
            pen_box.setWidth(4)
            font_text = QFont("Arial", 16, QFont.Weight.Bold)
            for cow in boxes:
                pts = cow["points"]
                cow_id = cow["id"]
                if len(pts) != 4:
                    continue
                polygon = QPolygonF([QPointF(p[0], p[1]) for p in pts])
                painter.setPen(pen_box)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPolygon(polygon)
                painter.setPen(QColor(255, 255, 0))
                painter.setFont(font_text)
                painter.drawText(int(pts[0][0]), int(pts[0][1]) - 10, f"ID: {cow_id}")
            painter.end()

        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self._update_time_label(video_frame_no)

    def _update_time_label(self, frame_no: int):
        fps = self.video_provider.fps or ANNOTATION_FPS
        total = self.video_provider.total_frames
        cur_sec = frame_no / fps
        tot_sec = total / fps
        cur_str = f"{int(cur_sec // 60):02d}:{int(cur_sec % 60):02d}"
        tot_str = f"{int(tot_sec // 60):02d}:{int(tot_sec % 60):02d}"
        self.lbl_time.setText(
            f"{cur_str} / {tot_str}  (frame {frame_no:,} / {total:,})"
        )

    # Playback
    def toggle_playback(self):
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.btn_play.setText("▶")
        else:
            interval_ms = int(1000 / (self.video_provider.fps * self._playback_speed))
            self.play_timer.start(max(1, interval_ms))
            self.btn_play.setText("⏸")

    def _advance_frame(self):
        cur = self.time_slider.value()
        if cur >= self.time_slider.maximum():
            self.play_timer.stop()
            self.btn_play.setText("▶")
            return
        self.time_slider.setValue(cur + 1)

    def _prev_frame(self):
        self.play_timer.stop()
        self.btn_play.setText("▶")
        cur = self.time_slider.value()
        if cur > 0:
            self.time_slider.setValue(cur - 1)

    def _next_frame(self):
        self.play_timer.stop()
        self.btn_play.setText("▶")
        cur = self.time_slider.value()
        if cur < self.time_slider.maximum():
            self.time_slider.setValue(cur + 1)

    def _set_speed(self, factor: float, clicked_btn: QPushButton):
        self._playback_speed = factor
        for btn in self.speed_buttons.values():
            btn.setChecked(btn is clicked_btn)
            btn.setStyleSheet(self._speed_btn_style(active=(btn is clicked_btn)))
        if self.play_timer.isActive():
            interval_ms = int(1000 / (self.video_provider.fps * self._playback_speed))
            self.play_timer.start(max(1, interval_ms))

    # Keyboard shortcuts
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.toggle_playback()
        elif key in (Qt.Key.Key_A, Qt.Key.Key_Left):
            self._prev_frame()
        elif key in (Qt.Key.Key_D, Qt.Key.Key_Right):
            self._next_frame()
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv[:1])
    window = CowTrackerApp()
    window.showMaximized()
    sys.exit(app.exec())
