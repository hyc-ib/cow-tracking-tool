import sys
import zipfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSlider, QLabel, QPushButton, QFileDialog
from PyQt6.QtCore import Qt


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.dataset = []

        self.setWindowTitle("Cattle Tracklet Merge Assistant")
        self.setGeometry(100, 100, 800, 500)

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
        main_layout.addWidget(self.image_placeholder, stretch=4)

        # Time Slider
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setValue(0)
        main_layout.addWidget(self.time_slider, stretch=1)
        self.time_slider.valueChanged.connect(self.slider_changed)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")

        if folder_path:
            # print(f"folder_path: {folder_path}")
            self.dataset = self.parse_folder(folder_path)
            total_frames = len(self.dataset)

            if total_frames > 0:
                self.time_slider.setMaximum(total_frames - 1)
                self.time_slider.setValue(0)
                self.image_placeholder.setText(
                    f"folder_path: {folder_path}\n"
                    f"total_frames: {total_frames}"
                )

    def slider_changed(self, value):
        if self.dataset and value < len(self.dataset):
            frame_data = self.dataset[value]
            img_path = frame_data['image_path']
            xml_path = frame_data['xml_path']

            self.image_placeholder.setText(
                f"Index: {value}\n\n"
                f"image_path:\n{img_path}\n\n"
                f"xml_path:\n{xml_path}"
            )

    def parse_folder(self, base_folder_path):
        base_path = Path(base_folder_path)
        zip_files = list(base_path.glob("*_xml.zip"))
        extracted_xml_dir = base_path / "temp_xml_extracted"

        if zip_files:
            if not extracted_xml_dir.exists():
                with zipfile.ZipFile(zip_files[0], 'r') as zip_ref:
                    zip_ref.extractall(extracted_xml_dir)
                    # print(f"extracted_xml_dir: {extracted_xml_dir}")

        jpg_paths = sorted(list(base_path.glob("frames/**/*.jpg")))

        paired_dataset = []
        for jpg_path in jpg_paths:
            file_base_name = jpg_path.stem
            corresponding_xml = extracted_xml_dir / f"{file_base_name}.xml"

            if corresponding_xml.exists():
                paired_dataset.append({
                    "frame_name": file_base_name,
                    "image_path": str(jpg_path),
                    "xml_path": str(corresponding_xml)
                })

        return paired_dataset


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CowTrackerApp()
    window.show()
    sys.exit(app.exec())
