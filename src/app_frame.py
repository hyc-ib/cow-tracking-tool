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
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QIntValidator, QPolygonF


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.dataset = {}
        self.current_frames = []

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
        self.image_label = QLabel("Please Select Folder First")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #f3f0df; border: 2px dashed #005088;"
            "font-size: 20px; color: #005088;"
        )
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
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
        main_layout.addLayout(bottom_bar)

        # Time Slider
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.valueChanged.connect(self.slider_changed)
        main_layout.addWidget(self.time_slider, stretch=1)

    def select_folder(self):
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
            self.dataset = {seq: [] for seq in sequence_folders}

            self.combo_timestamp.blockSignals(True)
            self.combo_timestamp.clear()
            self.combo_timestamp.addItems(sequence_folders)
            self.combo_timestamp.blockSignals(False)

            if sequence_folders:
                self.combo_timestamp.setCurrentIndex(0)  # default to first timestamp
                self.timestamp_changed(0)

    def timestamp_changed(self, index):
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
                            "points": shape.get("points", []),
                        }
                    )
        except Exception as e:
            print(f"Error parsing JSON: {e}")

        return cow_boxes

    def slider_changed(self, value):
        if self.current_frames and value < len(self.current_frames):
            frame_data = self.current_frames[value]
            img_path = frame_data["image_path"]
            json_path = frame_data["json_path"]

            real_frame = frame_data["frame_number"]
            self.lbl_frame.setText(f"Frame: {real_frame}")

            # Show Image
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                if os.path.exists(json_path):
                    cow_boxes = self.parse_cow_json(json_path)

                    painter = QPainter(pixmap)
                    pen_box = QPen(QColor(0, 255, 0))
                    pen_box.setWidth(4)
                    font_text = QFont("Arial", 16, QFont.Weight.Bold)

                    for cow in cow_boxes:
                        pts = cow["points"]
                        cow_id = cow["id"]

                        if len(pts) != 4:
                            continue

                        pyqt_points = [QPointF(p[0], p[1]) for p in pts]
                        polygon = QPolygonF(pyqt_points)

                        # green box
                        painter.setPen(pen_box)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawPolygon(polygon)

                        # yellow ID
                        painter.setPen(QColor(255, 255, 0))
                        painter.setFont(font_text)
                        painter.drawText(
                            int(pts[0][0]), int(pts[0][1]) - 10, f"ID: {cow_id}"
                        )

                    painter.end()

            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled_pixmap)

            selected_timestamp = self.combo_timestamp.currentText()
            self.setWindowTitle(
                f"Cattle Tracklet Merge Assistant - [{selected_timestamp}] - Index: {value} / {self.time_slider.maximum()}"
            )

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
