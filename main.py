import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                          QLabel, QFileDialog, QMessageBox, QHBoxLayout, 
                          QPushButton, QGridLayout, QColorDialog, QToolBar)
from PyQt6.QtGui import QImage, QPixmap, QIcon, QAction
from PyQt6.QtCore import Qt, QPoint, QSize, QBuffer
from PIL import Image
import io
import cv2
import numpy as np

from palette_editor import PaletteEditor
from plugin_manager import PluginManager

class SpriteCraftEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpriteCraft Editor")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize components
        self.palette_editor = PaletteEditor()
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_plugins()
        
        # Initialize UI components
        self.init_ui()
        
    def init_ui(self):
        """Initialize the main UI components"""
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        
        # Create left panel for tools
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.main_layout.addWidget(self.left_panel, 1)
        
        # Create canvas for image editing
        self.canvas = QLabel(self)
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(800, 600)
        self.canvas.setStyleSheet("QLabel { background-color: #2b2b2b; }")
        self.main_layout.addWidget(self.canvas, 4)
        
        # Create right panel for palette
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.main_layout.addWidget(self.right_panel, 1)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create menu bar
        self.create_menu()
        
        # Initialize palette view
        self.init_palette_view()
        
    def init_palette_view(self):
        """Initialize the palette view in the right panel"""
        palette_label = QLabel("Color Palette")
        self.right_layout.addWidget(palette_label)
        
        # Color grid
        self.color_grid = QGridLayout()
        color_widget = QWidget()
        color_widget.setLayout(self.color_grid)
        self.right_layout.addWidget(color_widget)
        
        # Add color button
        add_color_btn = QPushButton("Add Color")
        add_color_btn.clicked.connect(self.add_color)
        self.right_layout.addWidget(add_color_btn)
        
        # Sort palette button
        sort_palette_btn = QPushButton("Sort Palette")
        sort_palette_btn.clicked.connect(lambda: self.palette_editor.sort_palette())
        self.right_layout.addWidget(sort_palette_btn)
        
        # Extract palette button
        extract_palette_btn = QPushButton("Extract from Image")
        extract_palette_btn.clicked.connect(self.extract_palette)
        self.right_layout.addWidget(extract_palette_btn)
        
        self.right_layout.addStretch()
        
    def add_color(self):
        """Open color dialog and add selected color to palette"""
        color = QColorDialog.getColor()
        if color.isValid():
            self.palette_editor.add_color(
                color.red(),
                color.green(),
                color.blue()
            )
            self.update_palette_view()
            
    def extract_palette(self):
        """Extract palette from current image"""
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
            
        # Convert QPixmap to PIL Image
        qimage = self.canvas.pixmap().toImage()
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        qimage.save(buffer, "PNG")
        pil_image = Image.open(io.BytesIO(buffer.data()))
        
        # Extract palette
        self.palette_editor.extract_palette(pil_image)
        self.update_palette_view()
        
    def update_palette_view(self):
        """Update the palette view with current colors"""
        # Clear existing colors
        for i in reversed(range(self.color_grid.count())): 
            self.color_grid.itemAt(i).widget().setParent(None)
            
        # Add current colors
        for i, (r, g, b) in enumerate(self.palette_editor.palette):
            color_btn = QPushButton()
            color_btn.setFixedSize(30, 30)
            color_btn.setStyleSheet(
                f"background-color: rgb({r},{g},{b}); border: none;"
            )
            row = i // 4
            col = i % 4
            self.color_grid.addWidget(color_btn, row, col)
            
            # Right-click menu for color removal
            color_btn.setContextMenuPolicy(Qt.CustomContextMenu)
            color_btn.customContextMenuRequested.connect(
                lambda _, index=i: self.remove_color(index)
            )
            
    def remove_color(self, index):
        """Remove a color from the palette"""
        self.palette_editor.remove_color(index)
        self.update_palette_view()
        
    def create_toolbar(self):
        """Create the main toolbar with editing tools"""
        toolbar = self.addToolBar("Tools")
        toolbar.setMovable(False)
        
        # Add basic tools
        tools = [
            ("Open", "Open Image", self.open_image),
            ("Save", "Save Image", self.save_image),
            ("Crop", "Crop Image", self.crop_image),
            ("Remove BG", "Remove Background", self.remove_background),
            ("Export", "Export Sprite Sheet", self.export_sprite_sheet)
        ]
        
        for name, tooltip, callback in tools:
            action = QAction(name, self)
            action.setStatusTip(tooltip)
            action.triggered.connect(callback)
            toolbar.addAction(action)
            
    def create_menu(self):
        """Create the main menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_image)
        file_menu.addAction(save_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
    def open_image(self):
        """Open an image file"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if file_name:
            image = QImage(file_name)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(
                    self.canvas.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.canvas.setPixmap(scaled_pixmap)
            else:
                QMessageBox.critical(self, "Error", "Could not load image!")
                
    def save_image(self):
        """Save the current image"""
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image to save!")
            return
            
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            "",
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;All Files (*.*)"
        )
        
        if file_name:
            self.canvas.pixmap().save(file_name)
            
    def crop_image(self):
        """Crop the current image"""
        # TODO: Implement cropping functionality
        pass
        
    def remove_background(self):
        """Remove background from the current image"""
        # TODO: Implement background removal using DeepLabV3
        pass
        
    def export_sprite_sheet(self):
        """Export the current image as a sprite sheet"""
        # TODO: Implement sprite sheet export
        pass

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a modern look
    
    # Set dark theme palette
    palette = app.palette()
    palette.setColor(palette.Window, Qt.black)
    palette.setColor(palette.WindowText, Qt.white)
    palette.setColor(palette.Base, Qt.darkGray)
    palette.setColor(palette.AlternateBase, Qt.gray)
    palette.setColor(palette.ToolTipBase, Qt.white)
    palette.setColor(palette.ToolTipText, Qt.white)
    palette.setColor(palette.Text, Qt.white)
    palette.setColor(palette.Button, Qt.darkGray)
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.Link, Qt.blue)
    palette.setColor(palette.Highlight, Qt.blue)
    palette.setColor(palette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    try:
        editor = SpriteCraftEditor()
        editor.setWindowTitle("SpriteCraft Editor")
        editor.resize(1200, 800)
        editor.show()
        editor.raise_()  # Bring window to front
        return sys.exit(app.exec_())
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        return sys.exit(1)

if __name__ == "__main__":
    main()
