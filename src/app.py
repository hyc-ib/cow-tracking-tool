import sys
import os
import zipfile
from pathlib import Path
import xml.etree.ElementTree as xmlET
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSlider, QLabel, QPushButton, QFileDialog, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.dataset = []

        self.setWindowTitle("Cattle Tracklet Merge Assistant")
        self.setGeometry(100, 100, 900, 600)

        # Widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Button (Open Folder)
        self.btn_open = QPushButton("Click to Open Folder")
        self.btn_open.setStyleSheet(
            "font-size: 16px; padding: 10px; background-color: #005088; color: white; border-radius: 5px;")
        main_layout.addWidget(self.btn_open)
        self.btn_open.clicked.connect(self.select_folder)

        # Image Section
        self.image_placeholder = QLabel("Please Select Folder First")
        self.image_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_placeholder.setStyleSheet(
            "background-color: #f3f0df; border: 2px dashed #005088; font-size: 20px; color: #005088;")
        self.image_placeholder.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
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
            img_path = frame_data['image_path']
            xml_path = frame_data['xml_path']

            # Show Image
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                scaled_pixmap = pixmap.scaled(
                    self.image_placeholder.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_placeholder.setPixmap(scaled_pixmap)
                self.setWindowTitle(
                    f"Cattle Tracklet Merge Assistant - Frame: {value} / {self.time_slider.maximum()}")

            # Parse XML
            if os.path.exists(xml_path):
                cow_boxes = self.parse_cow_xml(xml_path)
                # print(f"Current Frame {value}, Cows count: {len(cow_boxes)}")

    def parse_folder(self, folder_path):
        base_path = Path(folder_path)
        zip_files = list(base_path.glob("*xml.zip"))
        temp_xml_dir = base_path / "temp_xml_extracted"

        if zip_files:
            if not temp_xml_dir.exists() or not any(temp_xml_dir.iterdir()):
                with zipfile.ZipFile(zip_files[0], 'r') as zip_ref:
                    zip_ref.extractall(temp_xml_dir)

        paired_dataset = []
        img_paths = sorted(list(base_path.glob("frames/**/*.jpg")))
        xml_paths_in_temp = list(temp_xml_dir.rglob("*.xml"))
        xml_dict = {x.stem: x for x in xml_paths_in_temp}
        for jpg_path in img_paths:
            file_base_name = jpg_path.stem
            if file_base_name in xml_dict:
                paired_dataset.append({
                    "frame_name": file_base_name,
                    "image_path": str(jpg_path),
                    "xml_path": str(xml_dict[file_base_name])
                })

        return paired_dataset

    def parse_cow_xml(self, xml_path):
        cow_boxes = []
        try:
            tree = xmlET.parse(xml_path)
            root = tree.getroot()
            for obj in root.findall('object'):
                cow_id = obj.find('name').text if obj.find(
                    'name') is not None else "Unknown"
                robndbox = obj.find('robndbox')
                if robndbox is not None:
                    cow_boxes.append({
                        "id": cow_id,
                        "cx": float(robndbox.find('cx').text),
                        "cy": float(robndbox.find('cy').text),
                        "w": float(robndbox.find('w').text),
                        "h": float(robndbox.find('h').text),
                        "angle": float(robndbox.find('angle').text)
                    })
        except Exception as e:
            print(f"Error parsing XML: {e}")

        return cow_boxes


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CowTrackerApp()
    window.show()
    sys.exit(app.exec())
