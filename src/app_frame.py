"""
Cattle Tracklet Merge Assistant (Frame Edition)

Folder structure expected:
  <camera1>/
    └── frames/
        └── <20250910T054951_20250910T061053>/
            └── <20250910T054951_20250910T061053_frame_0050>.jpg
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
    QSlider,
    QLabel,
    QPushButton,
    QFileDialog,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QPolygonF


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.dataset = []

        self.setWindowTitle("Cattle Tracklet Merge Assistant")
        self.setGeometry(100, 100, 1000, 700)

        # Widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Button (Open Folder)
        self.btn_open = QPushButton("Click to Open Folder")
        self.btn_open.setStyleSheet(
            "font-size: 16px; padding: 10px; background-color: #005088; color: white; border-radius: 5px;"
        )
        main_layout.addWidget(self.btn_open)
        self.btn_open.clicked.connect(self.select_folder)

        # Image Section
        self.image_placeholder = QLabel("Please Select Folder First")
        self.image_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_placeholder.setStyleSheet(
            "background-color: #f3f0df; border: 2px dashed #005088; font-size: 20px; color: #005088;"
        )
        self.image_placeholder.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        main_layout.addWidget(self.image_placeholder, stretch=4)

        # Time Slider
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setValue(0)
        main_layout.addWidget(self.time_slider, stretch=1)
        self.time_slider.valueChanged.connect(self.slider_changed)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Open")

        if folder_path:
            # print(f"folder_path: {folder_path}")
            self.dataset = self.parse_folder(folder_path)
            total_frames = len(self.dataset)

            if total_frames > 0:
                self.time_slider.setMaximum(total_frames - 1)
                self.time_slider.setValue(0)
                self.slider_changed(0)

    def slider_changed(self, value):
        if self.dataset and value < len(self.dataset):
            frame_data = self.dataset[value]
            img_path = frame_data["image_path"]
            json_path = frame_data["json_path"]

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
                    self.image_placeholder.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.image_placeholder.setPixmap(scaled_pixmap)
                self.setWindowTitle(
                    f"Cattle Tracklet Merge Assistant - Frame: {value} / {self.time_slider.maximum()}"
                )

    def parse_folder(self, folder_path):
        base_path = Path(folder_path)
        zip_files = list(base_path.glob("*json.zip"))
        temp_json_dir = base_path / "temp_json_extracted"

        if zip_files:
            if not temp_json_dir.exists() or not any(temp_json_dir.iterdir()):
                with zipfile.ZipFile(zip_files[0], "r") as zip_ref:
                    zip_ref.extractall(temp_json_dir)

        json_files = []
        if temp_json_dir.exists():
            json_files = list(temp_json_dir.rglob("*.json"))

        json_dict = {}
        for j in json_files:
            match = re.search(r"(.*)_frame_(\d+)", j.stem)
            if match:
                json_dict[(match.group(1), int(match.group(2)))] = j

        paired_dataset = []
        img_paths = sorted(list(base_path.glob("frames/**/*.jpg")))

        for jpg_path in img_paths:
            match = re.search(r"(.*)_frame_(\d+)", jpg_path.stem)
            if match:
                # match file name and frame number
                key = (match.group(1), int(match.group(2)))
                if key in json_dict:
                    paired_dataset.append(
                        {
                            "frame_name": jpg_path.stem,
                            "image_path": str(jpg_path),
                            "json_path": str(json_dict[key]),
                        }
                    )

        return paired_dataset

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CowTrackerApp()
    window.show()
    sys.exit(app.exec())
