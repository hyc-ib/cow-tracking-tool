"""
Cattle Tracklet Merge Assistant (Video Edition)

Folder structure expected:
  <camera1>_mask/
    ├── <20250910T054951_20250910T061053>.mp4
    └── <camera1>_xml.zip
"""

import sys
import re
import math
import zipfile
from pathlib import Path
import xml.etree.ElementTree as xmlET
import cv2
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
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QImage, QIntValidator


class VideoFrameProvider:
    def __init__(self):
        self.cap = None
        self.total_frames = 0
        self.fps = 25.0

    def open(self, video_path: str) -> bool:
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            return False
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        return True

    def get_frame(self, frame_no: int):
        if not self.cap or not self.cap.isOpened():
            return None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = self.cap.read()
        if not ret:
            return None
        # Convert BGR (OpenCV) to RGB (PyQt)
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
        self.xml_dict = {}
        self.base_folder_path = None
        self.temp_xml_dir = None

        # Window
        self.setWindowTitle("Cattle Tracklet Merge Assistant — Video Edition")
        self.setGeometry(100, 100, 1000, 700)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Top bar
        top_bar = QHBoxLayout()
        self.btn_open = QPushButton("Open Folder")
        self.btn_open.setStyleSheet(
            "font-size: 14px; padding: 8px 18px;"
            "background-color: #005088; color: white; border-radius: 5px;"
        )
        self.btn_open.clicked.connect(self.select_folder)
        top_bar.addWidget(self.btn_open)

        top_bar.addWidget(QLabel("Select Video:"))
        self.combo_video = QComboBox()
        self.combo_video.setMinimumWidth(300)
        self.combo_video.currentIndexChanged.connect(self.video_changed)
        top_bar.addWidget(self.combo_video)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # Image / Video display area
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

        # Bottom bar
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

        # Timeline slider
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.valueChanged.connect(self.slider_changed)
        main_layout.addWidget(self.time_slider, stretch=1)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Open Folder")
        if not folder_path:
            return

        self.base_folder_path = Path(folder_path)
        self.temp_xml_dir = self.base_folder_path / "temp_xml_extracted"

        # extract XML from zip
        zip_files = list(self.base_folder_path.glob("*xml.zip"))
        if zip_files:
            if not self.temp_xml_dir.exists() or not any(self.temp_xml_dir.iterdir()):
                with zipfile.ZipFile(zip_files[0], "r") as zip_ref:
                    zip_ref.extractall(self.temp_xml_dir)

        # sorted all mp4 files
        mp4_files = sorted(list(self.base_folder_path.glob("*.mp4")))

        if not mp4_files:
            self.image_label.setText("No .mp4 files found in this folder!")
            return

        # populate video combo box
        self.combo_video.blockSignals(True)
        self.combo_video.clear()
        for mp4 in mp4_files:
            self.combo_video.addItem(mp4.name, mp4)
        self.combo_video.blockSignals(False)
        self.combo_video.setCurrentIndex(0)  # default to first video
        self.video_changed(0)

    def video_changed(self, index):
        if index < 0:
            return

        # get the video path from combo box
        video_path = self.combo_video.itemData(index)
        if not video_path or not self.video_provider.open(str(video_path)):
            self.image_label.setText(f"Failed to open video:\n{video_path.name}")
            return

        self.int_validator.setTop(self.video_provider.total_frames - 1)
        self.time_slider.setMaximum(self.video_provider.total_frames - 1)
        self.xml_dict.clear()
        video_stem = video_path.stem

        # load XML files and pair them with video frames
        xml_paths = (
            list(self.temp_xml_dir.rglob("*.xml")) if self.temp_xml_dir.exists() else []
        )
        if not xml_paths:
            xml_paths = list(self.base_folder_path.glob("*.xml"))

        # pair XML files with video frames based on naming rules
        for xml_path in xml_paths:
            if video_stem in xml_path.stem:
                match = re.search(r"frame_(\d+)", xml_path.stem)
                if match:
                    frame_num = int(match.group(1))
                    self.xml_dict[frame_num] = xml_path

        # reset slider
        self.time_slider.setValue(0)
        self.slider_changed(0)

    def slider_changed(self, video_frame_no: int):
        pixmap = self.video_provider.get_frame(video_frame_no)
        if pixmap is None:
            return

        # paint bounding boxes if XML exists for this frame
        if video_frame_no in self.xml_dict:
            boxes = self.parse_cow_xml(str(self.xml_dict[video_frame_no]))

            painter = QPainter(pixmap)
            pen_box = QPen(QColor(0, 255, 0))
            pen_box.setWidth(4)
            painter.setPen(pen_box)
            painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))

            for cow in boxes:
                painter.save()
                painter.translate(cow["cx"], cow["cy"])
                painter.rotate(cow["angle"])
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    int(-cow["w"] / 2), int(-cow["h"] / 2), int(cow["w"]), int(cow["h"])
                )
                painter.setPen(QColor(255, 255, 0))
                painter.drawText(
                    int(-cow["w"] / 2), int(-cow["h"] / 2) - 10, f"ID: {cow['id']}"
                )
                painter.restore()
            painter.end()

        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        current_fps = self.video_provider.fps
        self.lbl_frame.setText(
            f"Frame: {video_frame_no:,} / {self.video_provider.total_frames:,}  |  🎬 FPS: {current_fps:.1f}"
        )

    def jump_to_frame(self):
        text = self.input_frame.text()
        if text:
            target_frame = int(text)
            max_frame = self.time_slider.maximum()

            if target_frame > max_frame:
                target_frame = max_frame
            elif target_frame < 0:
                target_frame = 0

            self.time_slider.setValue(target_frame)

            self.input_frame.clear()
            self.input_frame.clearFocus()

    def parse_cow_xml(self, xml_path: str) -> list:
        cow_boxes = []
        try:
            tree = xmlET.parse(xml_path)
            root = tree.getroot()
            for obj in root.findall("object"):
                cow_id = (
                    obj.find("name").text if obj.find("name") is not None else "Unknown"
                )
                robndbox = obj.find("robndbox")
                if robndbox is not None:
                    angle_rad = float(robndbox.find("angle").text)
                    cow_boxes.append(
                        {
                            "id": cow_id,
                            "cx": float(robndbox.find("cx").text),
                            "cy": float(robndbox.find("cy").text),
                            "w": float(robndbox.find("w").text),
                            "h": float(robndbox.find("h").text),
                            "angle": math.degrees(angle_rad),
                        }
                    )
        except Exception as e:
            print(f"Error parsing XML: {e}")

        return cow_boxes


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CowTrackerApp()
    window.show()
    sys.exit(app.exec())
