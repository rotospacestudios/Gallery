import sys
import os
import shutil
import concurrent.futures
import json
from PIL import Image
from tkinter import filedialog, Tk
import uuid
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QLabel, QScrollArea, QVBoxLayout, QWidget, QGridLayout, QHBoxLayout, QMenuBar, QAction, QMenu, QMessageBox, QCheckBox, QDialog, QDialogButtonBox
from PyQt5.QtGui import QPixmap, QImage, QTransform, QPainter, QColor
from PyQt5.QtCore import Qt, QEvent, QPropertyAnimation, pyqtProperty, QTimer, QRect

def resize_image(file_path, resized_path):
    # Create a unique dummy file to avoid conflicts
    dummy_file = os.path.join(os.getcwd(), "working_temp_" + str(uuid.uuid4()) + os.path.splitext(file_path)[-1])
    shutil.copy2(file_path, dummy_file)
    # Resize the dummy file
    with Image.open(dummy_file) as img:
        img.thumbnail((256, 256), Image.LANCZOS)
        img.save(resized_path)
    os.remove(dummy_file)  # Clean up the working file

def process_image(file_path, original_folder, cache_resized_folder, image_data):
    relative_path = os.path.relpath(file_path, original_folder)
    resized_path = os.path.join(cache_resized_folder, relative_path)
    # Check if the resized image already exists
    if os.path.exists(resized_path):
        print(f"Thumbnail already exists for {file_path}, skipping conversion.")
        return
    # Ensure the directory exists
    os.makedirs(os.path.dirname(resized_path), exist_ok=True)
    resize_image(file_path, resized_path)
    image_data.append({
        "original": os.path.abspath(file_path),
        "resized": os.path.abspath(resized_path)
    })
    print(f"Resized {file_path} to {resized_path}")

def resize_images_and_generate_json(original_folder, cache_resized_folder):
    image_data = []
    json_path = os.path.join(cache_resized_folder, "image_links.json")
    if os.path.exists(json_path):
        with open(json_path, 'r') as json_file:
            image_data = json.load(json_file)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for root, dirs, files in os.walk(original_folder):
            for file in files:
                if is_image(file):
                    file_path = os.path.join(root, file)
                    futures.append(executor.submit(process_image, file_path, original_folder, cache_resized_folder, image_data))
        concurrent.futures.wait(futures)
    # Save the JSON file
    with open(json_path, 'w') as json_file:
        json.dump(image_data, json_file, indent=4)
    print(f"JSON file saved at {json_path}")
    return json_path

def is_image(file_name):
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    _, ext = os.path.splitext(file_name)
    return ext.lower() in image_extensions


class AnimatedLabel(QLabel):
    def __init__(self, pixmap, original_path, parent):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.original_path = original_path
        self.setPixmap(pixmap)
        self._scale_factor = 1.0
        self.animation = QPropertyAnimation(self, b"scale_factor")
        self.animation.setDuration(200)
        self.hovered = False
        self.toggled = False
        self.parent_widget = parent

    @pyqtProperty(float)
    def scale_factor(self):
        return self._scale_factor

    @scale_factor.setter
    def scale_factor(self, value):
        self._scale_factor = value
        transform = QTransform().scale(value, value)
        self.setPixmap(self.original_pixmap.transformed(transform, Qt.SmoothTransformation))

    def enterEvent(self, event):
        if not self.hovered:
            self.hovered = True
            self.animation.stop()
            self.animation.setStartValue(1.0)
            self.animation.setEndValue(1.1)
            self.animation.start()
            self.parent_widget.reset_hover_states(self)
            self.parent_widget.show_large_image(self.original_path, self)
            self.parent_widget.show_notification(self.original_path, self)

    def leaveEvent(self, event):
        if self.hovered and not self.toggled:
            self.hovered = False
            self.animation.stop()
            self.animation.setStartValue(1.1)
            self.animation.setEndValue(1.0)
            self.animation.start()
            self.parent_widget.hide_large_image()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggled = not self.toggled
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.toggled:
            painter = QPainter(self)
            painter.setPen(QColor(255, 255, 0))
            rect = self.pixmap().rect()
            rect.moveCenter(self.rect().center())
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

    def resizeEvent(self, event):
        self.update()

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)
        self.update()

    def update(self):
        super().update()
        self.repaint()

class NotificationBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; border-radius: 10px; padding: 10px;")
        self.label = QLabel(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(1000)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.hide_notification)

    def show_notification(self, text, position):
        self.label.setText(text)
        self.adjustSize()
        if position == 'left':
            self.move(self.parent().width() - self.width() - 20, 20)
        else:
            self.move(20, 20)
        self.show()
        self.animation.start()
        self.timer.start()

    def hide_notification(self):
        self.timer.stop()
        self.hide()

class CopyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Copy Selected Images")
        self.setGeometry(100, 100, 300, 150)
        layout = QVBoxLayout(self)
        self.checkbox = QCheckBox("Use thumbnails instead for this copy", self)
        layout.addWidget(self.checkbox)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

class ImageGallery(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Gallery")
        self.setGeometry(100, 100, 800, 600)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.widget = QWidget()
        self.layout = QGridLayout(self.widget)
        self.widget.setLayout(self.layout)
        self.scroll_area.setWidget(self.widget)
        self.setCentralWidget(self.scroll_area)
        self.images = []
        self.image_data = []
        self.scroll_area.viewport().installEventFilter(self)
        self.notification_box = NotificationBox(self)
        self.large_image_label = QLabel(self)
        self.large_image_label.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.large_image_label.hide()
        self.create_menu()

    def create_menu(self):
        menubar = self.menuBar()
        edit_menu = menubar.addMenu("Edit")
        clear_action = QAction("Clear Toggles", self)
        clear_action.triggered.connect(self.clear_toggles)
        edit_menu.addAction(clear_action)
        copy_action = QAction("Copy Selected to", self)
        copy_action.triggered.connect(self.copy_selected_to)
        edit_menu.addAction(copy_action)

    def clear_toggles(self):
        for label in self.images:
            if label.toggled:
                label.toggled = False
                label.update()

    def copy_selected_to(self):
        dialog = CopyDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            use_thumbnails = dialog.checkbox.isChecked()
            folder = QFileDialog.getExistingDirectory(self, "Select Folder")
            if folder:
                for label in self.images:
                    if label.toggled:
                        src = label.original_path if not use_thumbnails else label.original_pixmap
                        dst = os.path.join(folder, os.path.basename(label.original_path))
                        if use_thumbnails:
                            label.pixmap().save(dst)
                        else:
                            shutil.copy2(src, dst)
                QMessageBox.information(self, "Copy Completed", "Selected images have been copied successfully.")

    def load_json(self, json_path):
        with open(json_path, "r") as file:
            data = json.load(file)
            self.image_data = data
            self.display_images()
    def display_images(self):
        if not self.image_data:
            QMessageBox.warning(self, "No Images Found", "No images were found in the selected folder.")
            return

        for item in self.image_data:
            img_path = item["resized"]
            img = Image.open(img_path)
            img.thumbnail((150, 150))
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)
            label = AnimatedLabel(pixmap, item["original"], self)
            label.setAlignment(Qt.AlignCenter)  # Center the image
            label.setVisible(False)
            self.images.append(label)
        self.reposition_images()

    def reposition_images(self):
        width = self.scroll_area.viewport().width()
        columns = max(1, width // 160)
        for index, label in enumerate(self.images):
            row = index // columns
            column = index % columns
            self.layout.addWidget(label, row, column)
        self.lazy_load_images()

    def lazy_load_images(self):
        viewport_rect = self.scroll_area.viewport().rect()
        for label in self.images:
            if label.isVisible():
                continue
            label_rect = self.scroll_area.viewport().mapFromGlobal(label.mapToGlobal(label.rect().topLeft()))
            if viewport_rect.intersects(QRect(label_rect, label.size())):
                label.setVisible(True)

    def reset_hover_states(self, current_label):
        for label in self.images:
            if label != current_label and label.hovered:
                label.leaveEvent(None)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Resize and source is self.scroll_area.viewport():
            self.reposition_images()
            self.update_large_image_position()
        elif event.type() == QEvent.Leave and source is self.scroll_area.viewport():
            self.reset_hover_states(None)
        elif event.type() == QEvent.Scroll and source is self.scroll_area.viewport():
            self.lazy_load_images()
        return super().eventFilter(source, event)

    def show_notification(self, image_path, label):
        folder_name = os.path.basename(os.path.dirname(image_path))
        file_name = os.path.basename(image_path)
        label_rect = label.geometry()
        if label_rect.center().x() > self.width() // 2:
            position = 'left'
        else:
            position = 'right'
        self.notification_box.show_notification(f"{folder_name}/{file_name}", position)

    def show_large_image(self, image_path, label):
        img = Image.open(image_path)
        img = img.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        self.large_image_label.setPixmap(pixmap.scaled(self.large_image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.update_large_image_position(label)
        self.large_image_label.show()

    def hide_large_image(self):
        self.large_image_label.hide()

    def update_large_image_position(self, label=None):
        if label:
            label_rect = label.geometry()
            if label_rect.center().x() > self.width() // 2:
                self.large_image_label.setGeometry(0, 0, self.width() // 2, self.height())
            else:
                self.large_image_label.setGeometry(self.width() // 2, 0, self.width() // 2, self.height())
        else:
            self.large_image_label.setGeometry(self.width() // 2, 0, self.width() // 2, self.height())

def main():
    root = Tk()
    root.withdraw()  # Hide the root window
    original_folder = filedialog.askdirectory(title="Select Original Image Folder")
    if not original_folder:
        print("No directory selected. Exiting.")
        return
    cache_resized_folder = os.path.join(os.getcwd(), "cache", "resized", os.path.basename(original_folder))
    json_path = resize_images_and_generate_json(original_folder, cache_resized_folder)

    app = QApplication(sys.argv)
    gallery = ImageGallery()
    gallery.load_json(json_path)
    gallery.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
