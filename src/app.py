import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSlider, QLabel
from PyQt6.QtCore import Qt


class CowTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cattle Tracklet Merge Assistant")
        self.setGeometry(100, 100, 800, 400)  # (x, y, width, height)

        # Widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Display
        self.image_placeholder = QLabel("Frame: 0", self)
        self.image_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_placeholder.setStyleSheet(
            "background-color: #f3f0df; border: 2px dashed #005088; font-size: 24px; color: #005088;")
        layout.addWidget(self.image_placeholder, stretch=4)

        # Time Slider
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)  # frame start position
        self.time_slider.setMaximum(100)  # frame end position (default 100)
        self.time_slider.setValue(0)
        self.time_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.time_slider.setTickInterval(10)
        layout.addWidget(self.time_slider, stretch=1)

        # Signal to Slot
        self.time_slider.valueChanged.connect(self.slider_changed)

    def slider_changed(self, value):
        self.image_placeholder.setText(f"Frame: {value}")
        # print(f"User scrubbed to frame: {value}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CowTrackerApp()
    window.show()
    sys.exit(app.exec())
