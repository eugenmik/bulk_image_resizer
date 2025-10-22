import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QFileDialog, QProgressBar, QTextEdit, QCheckBox, QLabel
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PIL import Image

def resource_path(relative_path):
    """ Get the absolute path to a resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class Worker(QThread):
    """ A worker thread to handle image processing without freezing the GUI """
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, input_dir, output_dir, target_size, jpeg_quality, overwrite):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.target_size = target_size
        self.jpeg_quality = jpeg_quality
        self.overwrite = overwrite

    def run(self):
        try:
            input_path = Path(self.input_dir)
            output_path = Path(self.output_dir) if not self.overwrite else None

            if not self.overwrite and output_path and not output_path.exists():
                output_path.mkdir(parents=True, exist_ok=True)

            image_files = list(input_path.glob("*.jpg")) + \
                          list(input_path.glob("*.jpeg")) + \
                          list(input_path.glob("*.png"))

            total = len(image_files)
            if total == 0:
                self.log.emit("No images found in the source folder.")
                self.finished.emit()
                return

            for i, img_path in enumerate(image_files):
                try:
                    with Image.open(img_path) as img:
                        # Strip metadata
                        if hasattr(img, 'info'):
                            img.info.clear()

                        width, height = img.size
                        current_max = max(width, height)

                        if current_max <= self.target_size:
                            new_img = img.copy()
                        else:
                            ratio = self.target_size / current_max
                            new_size = (int(width * ratio), int(height * ratio))
                            new_img = img.resize(new_size, Image.LANCZOS)

                        # Strip metadata from the new image as well
                        if hasattr(new_img, 'info'):
                            new_img.info.clear()

                        # Define save path
                        save_path = img_path if self.overwrite else output_path / img_path.name
                        
                        ext = save_path.suffix.lower()
                        if ext in ('.jpg', '.jpeg'):
                            # Convert to RGB if necessary (for formats like RGBA or P)
                            if new_img.mode in ("RGBA", "P"):
                                background = Image.new("RGB", new_img.size, (255, 255, 255))
                                if new_img.mode == "RGBA":
                                    background.paste(new_img, mask=new_img.split()[-1])
                                else:
                                    background.paste(new_img)
                                new_img = background
                            
                            # Save with user-defined quality
                            new_img.save(save_path, "JPEG", quality=self.jpeg_quality, optimize=True)

                        else:  # PNG
                            new_img.save(save_path, "PNG", optimize=True)

                        self.log.emit(f"Processed: {img_path.name}")
                except Exception as e:
                    self.log.emit(f"Error with {img_path.name}: {str(e)}")

                self.progress.emit(int((i + 1) / total * 100))

            self.log.emit("Conversion completed.")
        except Exception as e:
            self.log.emit(f"Critical error: {str(e)}")
        finally:
            self.finished.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setWindowTitle("Bulk Image Resizer")
        self.setFixedSize(620, 750) # Adjusted height after removing footer
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header Image
        header_label = QLabel()
        header_pixmap = QPixmap(resource_path("header.png"))
        if not header_pixmap.isNull():
            header_label.setPixmap(header_pixmap.scaled(600, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            layout.addWidget(header_label)

        # Source Folder
        layout.addWidget(QLabel("Select the source folder containing your images:"))
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Path to source folder...")
        input_btn = QPushButton("Browse...")
        input_btn.clicked.connect(self.select_input_folder)
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_line)
        input_layout.addWidget(input_btn)
        layout.addLayout(input_layout)

        # Destination Folder
        layout.addWidget(QLabel("Select the destination folder for the resized images:"))
        self.output_line = QLineEdit()
        self.output_line.setPlaceholderText("Path to destination folder...")
        self.output_btn = QPushButton("Browse...")
        self.output_btn.clicked.connect(self.select_output_folder)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_line)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)

        # Target Size
        layout.addWidget(QLabel("Enter the target size for the longest side (in pixels):"))
        self.size_line = QLineEdit()
        self.size_line.setPlaceholderText("e.g., 1920")
        self.size_line.setText("1920") # Default value
        layout.addWidget(self.size_line)
        
        # JPEG Quality
        layout.addWidget(QLabel("Image quality for JPEG (1-95):"))
        self.quality_line = QLineEdit()
        self.quality_line.setPlaceholderText("e.g., 80")
        self.quality_line.setText("80") # Default value
        layout.addWidget(self.quality_line)
        
        # Overwrite Checkbox
        self.overwrite_cb = QCheckBox("Overwrite original images")
        self.overwrite_cb.stateChanged.connect(self.toggle_output)
        layout.addWidget(self.overwrite_cb)

        # Start Button
        self.start_btn = QPushButton("START")
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.start_btn)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log Window
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.setLayout(layout)

    def toggle_output(self, state):
        enabled = not (state == Qt.Checked)
        self.output_line.setEnabled(enabled)
        self.output_btn.setEnabled(enabled)

    def select_input_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            self.input_line.setText(folder)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.output_line.setText(folder)

    def start_conversion(self):
        input_dir = self.input_line.text().strip()
        output_dir = self.output_line.text().strip()
        size_text = self.size_line.text().strip()
        quality_text = self.quality_line.text().strip()
        overwrite = self.overwrite_cb.isChecked()

        if not input_dir or not os.path.isdir(input_dir):
            self.log_text.append("Error: Invalid source folder.")
            return

        if not overwrite and (not output_dir or not os.path.isdir(output_dir)):
            self.log_text.append("Error: Invalid destination folder.")
            return

        if not size_text.isdigit() or int(size_text) <= 0:
            self.log_text.append("Error: Please enter a valid number greater than 0 for the image size.")
            return

        if not quality_text.isdigit() or not (1 <= int(quality_text) <= 95):
            self.log_text.append("Error: Image quality must be a number between 1 and 95.")
            return

        target_size = int(size_text)
        jpeg_quality = int(quality_text)

        self.start_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        self.worker = Worker(input_dir, output_dir, target_size, jpeg_quality, overwrite)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log_text.append)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self):
        self.start_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
    