# main.py

from PyQt6.QtWidgets import (QMainWindow, QApplication, QFileDialog, QMessageBox, QColorDialog, 
                          QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSlider, QPushButton, QGroupBox, 
                          QDockWidget, QWidget, QFrame, QSizePolicy, QLineEdit, QMenu, QToolBar)
from PyQt6.QtGui import QIcon, QAction, QImage, QPixmap, QPainter, QPen, QColor, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QPoint, QSize, QRect, QBuffer, pyqtSignal
import sys
import json
import io  # used for converting byte data to PIL Image object
import cv2
import numpy as np
from PIL import Image
from palette_editor import PaletteEditor
from plugin_manager import PluginManager
from image_processor import ImageProcessor
from sprite_sheet import SpriteSheetGenerator

class EditableLabel(QLabel):
    """A custom QLabel to handle image editing operations."""
    cropping_finished = pyqtSignal(QRect)  # Signal emitted with the final crop QRect
    hover_region_detected = pyqtSignal(QRect)  # Signal emitted when hovering over a potential background region
    image_updated = pyqtSignal()  # Signal emitted when the image is updated
    
    # Tool modes
    MODE_NONE = 0
    MODE_CROP = 1
    MODE_BRUSH = 2
    MODE_AUTO_DETECT = 3
    MODE_PENCIL = 4
    MODE_ERASER = 5
    MODE_FILL = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QLabel { background-color: #2b2b2b; color: white; }")
        
        self._pixmap = None  # Store the original pixmap
        self._working_pixmap = None  # Pixmap for editing operations
        self._mask = None  # Mask for transparency
        
        # Tool state
        self._mode = self.MODE_NONE
        self._brush_size = 20
        self._brush_hardness = 0.5
        self._start_point = None
        self._end_point = None
        self._current_rect = QRect()
        self._last_pos = None
        
        # History for undo/redo
        self._history = []  # List of previous states (pixmaps)
        self._history_index = -1  # Current position in history
        self._max_history = 20  # Maximum number of history states to keep
        
        # Add welcome text
        self.setText("Welcome to SpriteCraft Editor\nUse File > Open to load an image")

    def setPixmap(self, pixmap: QPixmap):
        """Sets the pixmap and stores it."""
        self._pixmap = pixmap
        self._working_pixmap = QPixmap(pixmap)
        
        # Create mask for transparency (initially all opaque)
        self._mask = QImage(pixmap.size(), QImage.Format.Format_Alpha8)
        self._mask.fill(255)  # 255 = fully opaque
        
        # Clear text when setting an image
        self.setText("")
        
        # Apply default zoom (50%)
        self._zoom_level = 0.5  # Set default zoom to 50%
        
        # Scale the pixmap
        scaled_pixmap = pixmap.scaled(
            int(pixmap.width() * self._zoom_level),
            int(pixmap.height() * self._zoom_level),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Store unzoomed pixmap for future zoom operations
        self._unzoomed_pixmap = QPixmap(self._working_pixmap)
        
        # Clear history when setting a new image
        self._history = []
        self._history_index = -1
        
        # Add initial state to history
        self._add_to_history()
        
        # Display the scaled pixmap
        super().setPixmap(scaled_pixmap)
        self.adjustSize()  # Adjust label size to fit pixmap if needed
    
    def pixmap(self):
        """Returns the current working pixmap."""
        return self._working_pixmap
    
    def original_pixmap(self):
        """Returns the original unmodified pixmap."""
        return self._pixmap
    
    def set_mode(self, mode):
        """Set the current editing mode."""
        self._mode = mode
        self._start_point = None
        self._end_point = None
        self._current_rect = QRect()
        self._last_pos = None
        
        # Set cursor based on mode
        if mode == self.MODE_BRUSH:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == self.MODE_CROP:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
        self.update()
    
    def set_brush_size(self, size):
        """Set the brush size."""
        self._brush_size = size
    
    def set_brush_hardness(self, hardness):
        """Set the brush hardness (0.0 to 1.0)."""
        self._brush_hardness = max(0.0, min(1.0, hardness))

    def mousePressEvent(self, event):
        if not self._pixmap or self._pixmap.isNull():
            super().mousePressEvent(event)
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            
            if self._mode == self.MODE_CROP:
                # Start crop operation
                self._start_point = pos
                self._end_point = self._start_point
                self._current_rect = QRect(self._start_point, self._end_point).normalized()
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_BRUSH:
                # Start brush operation
                self._last_pos = pos
                self._apply_brush(pos)
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_PENCIL:
                # Start drawing operation
                self._last_pos = pos
                self._draw_pixel(pos)
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_ERASER:
                # Start erasing operation
                self._last_pos = pos
                self._erase_pixel(pos)
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_FILL:
                # Fill operation
                self._fill_area(pos)
                self.update()
                event.accept()
                
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._pixmap or self._pixmap.isNull():
            super().mouseMoveEvent(event)
            return
            
        pos = event.position().toPoint()
        self._last_pos = pos  # Always update last position for cursor tracking
        
        # Auto-detect background region on hover
        if self._mode == self.MODE_AUTO_DETECT:
            # Always update to show cursor highlight
            self.update()
            
            # Get color at current position
            if self._pixmap and not self._pixmap.isNull():
                # Find region with similar color
                if not event.buttons() & Qt.MouseButton.LeftButton:
                    # Only show preview when not drawing
                    self._highlight_region(pos, None)
                elif self._last_pos is not None:
                    # If mouse button is pressed, remove the detected region
                    self._remove_region(pos)
                    self.update()
            
        # Handle other mouse move events
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._mode == self.MODE_CROP and self._start_point is not None:
                # Update crop rectangle
                self._end_point = pos
                self._current_rect = QRect(self._start_point, self._end_point).normalized()
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_BRUSH and self._last_pos is not None:
                # Draw line from last position to current position
                self._draw_line(self._last_pos, pos)
                self._last_pos = pos
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_PENCIL and self._last_pos is not None:
                # Draw pixel line from last position to current position
                self._draw_pixel_line(self._last_pos, pos)
                self._last_pos = pos
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_ERASER and self._last_pos is not None:
                # Erase pixel line from last position to current position
                self._erase_pixel_line(self._last_pos, pos)
                self._last_pos = pos
                self.update()
                event.accept()
                
            else:
                super().mouseMoveEvent(event)
        else:
            self._last_pos = pos  # Track position even when not drawing
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._pixmap or self._pixmap.isNull():
            super().mouseReleaseEvent(event)
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            if self._mode == self.MODE_CROP and self._start_point is not None:
                # Finish crop operation
                self._end_point = event.position().toPoint()
                final_rect = QRect(self._start_point, self._end_point).normalized()

                if self.pixmap() and not self.pixmap().isNull():
                    scaled_pixmap = super().pixmap()
                    pixmap_rect = scaled_pixmap.rect()

                    if pixmap_rect.isValid() and scaled_pixmap.width() > 0 and scaled_pixmap.height() > 0:
                        x_scale = self.pixmap().width() / scaled_pixmap.width()
                        y_scale = self.pixmap().height() / scaled_pixmap.height()

                        x_offset = (self.width() - scaled_pixmap.width()) // 2
                        y_offset = (self.height() - scaled_pixmap.height()) // 2

                        relative_rect = QRect(final_rect.topLeft() - QPoint(x_offset, y_offset), final_rect.size())

                        crop_x = int(relative_rect.x() * x_scale)
                        crop_y = int(relative_rect.y() * y_scale)
                        crop_width = int(relative_rect.width() * x_scale)
                        crop_height = int(relative_rect.height() * y_scale)

                        crop_x = max(0, crop_x)
                        crop_y = max(0, crop_y)
                        crop_width = min(crop_width, self.pixmap().width() - crop_x)
                        crop_height = min(crop_height, self.pixmap().height() - crop_y)

                        if crop_width > 0 and crop_height > 0:
                            self.cropping_finished.emit(QRect(crop_x, crop_y, crop_width, crop_height))

                self._start_point = None
                self._end_point = None
                self._current_rect = QRect()
                self.update()
                event.accept()
                
            elif self._mode == self.MODE_BRUSH:
                # Finish brush operation
                self._last_pos = None
                self.update()
                event.accept()
                
            else:
                super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)
            
    def _apply_brush(self, pos):
        """Apply brush at the given position."""
        if not self._pixmap or not self._mask:
            return
            
        # Create painter for the mask
        painter = QPainter(self._mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Set up the brush
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0))  # Black = transparent
        
        # Draw circle at position
        painter.drawEllipse(pos, self._brush_size, self._brush_size)
        painter.end()
        
        # Apply the updated mask to the working pixmap
        self._update_working_pixmap()
        
    def _draw_line(self, start_pos, end_pos):
        """Draw a line with the brush from start to end position."""
        if not self._pixmap or not self._mask:
            return
            
        # Create painter for the mask
        painter = QPainter(self._mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Set up the brush
        pen = QPen(QColor(0, 0, 0), self._brush_size * 2)  # Black = transparent
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # Draw line
        painter.drawLine(start_pos, end_pos)
        painter.end()
        
        # Apply the updated mask to the working pixmap
        self._update_working_pixmap()
        
        # Signal that the image has been updated
        if hasattr(self, 'image_updated') and callable(self.image_updated):
            self.image_updated.emit()
        
    def _update_working_pixmap(self):
        """Update the working pixmap with the current mask."""
        if not self._pixmap or not self._mask:
            return
            
        # Create a copy of the original pixmap
        self._working_pixmap = QPixmap(self._pixmap)
        
        # Create a painter for the working pixmap
        painter = QPainter(self._working_pixmap)
        
        # Set the mask as the opacity mask
        painter.setOpacity(1.0)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, self._mask)
        painter.end()
        
        # Add to history
        self._add_to_history()
        
        # Update the display
        super().setPixmap(self._working_pixmap)
        
        # Emit signal that image has been updated
        self.image_updated.emit()
        
    def _add_to_history(self):
        """Add current state to history."""
        if not self._working_pixmap:
            return
            
        # If we're not at the end of the history, remove future states
        if self._history_index < len(self._history) - 1:
            self._history = self._history[:self._history_index + 1]
            
        # Add current state to history
        self._history.append(QPixmap(self._working_pixmap))
        self._history_index = len(self._history) - 1
        
        # Limit history size
        if len(self._history) > self._max_history:
            self._history.pop(0)
            self._history_index -= 1
            
    def undo(self):
        """Undo the last operation."""
        if self._history_index > 0:
            self._history_index -= 1
            self._restore_from_history()
            return True
        return False
            
    def redo(self):
        """Redo the previously undone operation."""
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._restore_from_history()
            return True
        return False
            
    def _restore_from_history(self):
        """Restore state from history at current index."""
        if 0 <= self._history_index < len(self._history):
            # Restore working pixmap from history
            self._working_pixmap = QPixmap(self._history[self._history_index])
            self._unzoomed_pixmap = QPixmap(self._working_pixmap)
            
            # Apply current zoom
            scaled_pixmap = self._working_pixmap.scaled(
                int(self._working_pixmap.width() * self._zoom_level),
                int(self._working_pixmap.height() * self._zoom_level),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Update display
            super().setPixmap(scaled_pixmap)
            
            # Signal that image has been updated
            self.image_updated.emit()
        
    def _draw_pixel(self, pos):
        """Draw a pixel at the given position."""
        if not self._pixmap or self._pixmap.isNull():
            return
            
        # Create a copy of the working pixmap if needed
        if not self._working_pixmap:
            self._working_pixmap = QPixmap(self._pixmap)
            
        # Create painter for the working pixmap
        painter = QPainter(self._working_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # Disable antialiasing for pixel art
        
        # Set up the pen for pixel drawing
        pen = QPen(QColor(255, 0, 0))  # Use red for now, will be replaced with selected color
        pen.setWidth(1)
        painter.setPen(pen)
        
        # Draw the pixel
        painter.drawPoint(pos)
        painter.end()
        
        # Update the display
        super().setPixmap(self._working_pixmap)
        
        # Emit signal that image has been updated
        self.image_updated.emit()
        
    def _draw_pixel_line(self, start_pos, end_pos):
        """Draw a pixel line from start to end position."""
        if not self._pixmap or self._pixmap.isNull():
            return
            
        # Create a copy of the working pixmap if needed
        if not self._working_pixmap:
            self._working_pixmap = QPixmap(self._pixmap)
            
        # Create painter for the working pixmap
        painter = QPainter(self._working_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # Disable antialiasing for pixel art
        
        # Set up the pen for pixel drawing
        pen = QPen(QColor(255, 0, 0))  # Use red for now, will be replaced with selected color
        pen.setWidth(1)
        painter.setPen(pen)
        
        # Draw the line
        painter.drawLine(start_pos, end_pos)
        painter.end()
        
        # Update the display
        super().setPixmap(self._working_pixmap)
        
        # Emit signal that image has been updated
        self.image_updated.emit()
        
    def _erase_pixel(self, pos):
        """Erase pixels at the given position."""
        if not self._pixmap or self._pixmap.isNull():
            return
            
        # Create a copy of the working pixmap if needed
        if not self._working_pixmap:
            self._working_pixmap = QPixmap(self._pixmap)
            
        # Create painter for the working pixmap
        painter = QPainter(self._working_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # Disable antialiasing for pixel art
        
        # Set up the pen for erasing (transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        
        # Draw a rectangle at the position with the brush size
        size = self._brush_size
        painter.drawRect(pos.x() - size//2, pos.y() - size//2, size, size)
        painter.end()
        
        # Update the display
        super().setPixmap(self._working_pixmap)
        
        # Emit signal that image has been updated
        self.image_updated.emit()
        
    def _erase_pixel_line(self, start_pos, end_pos):
        """Erase pixels along a line from start to end position."""
        if not self._pixmap or self._pixmap.isNull():
            return
            
        # Create a copy of the working pixmap if needed
        if not self._working_pixmap:
            self._working_pixmap = QPixmap(self._pixmap)
            
        # Create painter for the working pixmap
        painter = QPainter(self._working_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # Disable antialiasing for pixel art
        
        # Set up the pen for erasing (transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        pen = QPen()
        pen.setWidth(self._brush_size)
        painter.setPen(pen)
        
        # Draw the line
        painter.drawLine(start_pos, end_pos)
        painter.end()
        
        # Update the display
        super().setPixmap(self._working_pixmap)
        
        # Emit signal that image has been updated
        self.image_updated.emit()
        
    def _fill_area(self, pos):
        """Fill an area with the selected color."""
        if not self._pixmap or self._pixmap.isNull():
            return
            
        # Create a copy of the working pixmap if needed
        if not self._working_pixmap:
            self._working_pixmap = QPixmap(self._pixmap)
            
        # Get the image as QImage for pixel access
        image = self._working_pixmap.toImage()
        
        # Get the target color at the clicked position
        target_color = image.pixelColor(pos)
        
        # Get the fill color (red for now, will be replaced with selected color)
        fill_color = QColor(255, 0, 0)
        
        # Skip if colors are the same
        if target_color == fill_color:
            return
            
        # Use flood fill algorithm
        width = image.width()
        height = image.height()
        
        # Convert to numpy array for faster processing
        ptr = image.constBits()
        ptr.setsize(image.bytesPerLine() * height)
        img_array = np.array(ptr).reshape(height, width, 4)
        
        # Create a mask for the flood fill
        mask = np.zeros((height + 2, width + 2), dtype=np.uint8)
        
        # Convert to BGR for OpenCV
        bgr_img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        
        # Perform flood fill
        r, g, b = fill_color.red(), fill_color.green(), fill_color.blue()
        cv2.floodFill(bgr_img, mask, (pos.x(), pos.y()), (b, g, r))
        
        # Convert back to RGBA
        result = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGBA)
        
        # Create QImage from the result
        bytes_per_line = 4 * width
        result_image = QImage(result.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888)
        
        # Update the working pixmap
        self._working_pixmap = QPixmap.fromImage(result_image)
        
        # Update the display
        super().setPixmap(self._working_pixmap)
        
        # Emit signal that image has been updated
        self.image_updated.emit()

    def paintEvent(self, event):
        """Paints the pixmap and any active tool overlays."""
        super().paintEvent(event)  # Paint the base QLabel (which draws the pixmap)
        
        if not self._pixmap or self._pixmap.isNull():
            return
            
        painter = QPainter(self)
        
        # Draw crop rectangle if in crop mode
        if self._mode == self.MODE_CROP and not self._current_rect.isNull():
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine))  # Red dashed line
            painter.setBrush(QColor(255, 0, 0, 50))  # Semi-transparent red fill
            painter.drawRect(self._current_rect)
            
        # Draw brush preview if in brush mode
        elif self._mode == self.MODE_BRUSH and self._last_pos is not None:
            # Draw a bright outline around the brush
            painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(255, 255, 255, 30))  # Very transparent white
            painter.drawEllipse(self._last_pos, self._brush_size, self._brush_size)
            
            # Draw a second, inner circle to make it more visible
            painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self._last_pos, self._brush_size - 2, self._brush_size - 2)
            
        # Draw pencil cursor if in pencil mode
        elif self._mode == self.MODE_PENCIL and self._last_pos is not None:
            # Draw a crosshair cursor
            painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine))
            painter.drawLine(self._last_pos.x() - 5, self._last_pos.y(), self._last_pos.x() + 5, self._last_pos.y())
            painter.drawLine(self._last_pos.x(), self._last_pos.y() - 5, self._last_pos.x(), self._last_pos.y() + 5)
            
            # Draw a pixel indicator
            painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.PenStyle.SolidLine))
            painter.drawRect(self._last_pos.x(), self._last_pos.y(), 1, 1)
            
        # Draw eraser cursor if in eraser mode
        elif self._mode == self.MODE_ERASER and self._last_pos is not None:
            # Draw eraser outline
            painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(255, 255, 255, 30))
            size = self._brush_size
            painter.drawRect(self._last_pos.x() - size//2, self._last_pos.y() - size//2, size, size)
            
        # Draw fill cursor if in fill mode
        elif self._mode == self.MODE_FILL and self._last_pos is not None:
            # Draw fill tool indicator
            painter.setPen(QPen(QColor(255, 255, 0), 1, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(255, 255, 0, 100))
            painter.drawEllipse(self._last_pos, 3, 3)
            
            # Draw radiating lines
            for i in range(0, 360, 45):
                angle = i * 3.14159 / 180
                x2 = self._last_pos.x() + 10 * np.cos(angle)
                y2 = self._last_pos.y() + 10 * np.sin(angle)
                painter.drawLine(self._last_pos.x(), self._last_pos.y(), int(x2), int(y2))
            
        # Draw region highlight if in auto-detect mode
        elif self._mode == self.MODE_AUTO_DETECT and self._last_pos is not None:
            # Always draw a highlight around the cursor for immediate feedback
            painter.setPen(QPen(QColor(0, 255, 255), 2, Qt.PenStyle.DashLine))  # Cyan dashed line
            painter.setBrush(QColor(0, 255, 255, 30))  # Semi-transparent cyan fill
            
            # Draw a highlight rectangle around the cursor
            cursor_rect = QRect(
                self._last_pos.x() - 30,
                self._last_pos.y() - 30,
                60, 60
            )
            painter.drawRect(cursor_rect)
            
            # Draw the detected region if available
            if hasattr(self, '_highlight_rect') and not self._highlight_rect.isNull():
                painter.setPen(QPen(QColor(255, 0, 255), 2, Qt.PenStyle.DashLine))  # Magenta dashed line
                painter.setBrush(QColor(255, 0, 255, 20))  # Semi-transparent magenta fill
                painter.drawRect(self._highlight_rect)
            
            # Draw cursor indicator
            painter.setPen(QPen(QColor(0, 255, 255), 1, Qt.PenStyle.SolidLine))
            painter.setBrush(QColor(0, 255, 255, 100))
            painter.drawEllipse(self._last_pos, 5, 5)
            
        painter.end()
        
    def _map_to_image_coords(self, pos):
        """Map screen coordinates to image coordinates."""
        if not self._pixmap or self._pixmap.isNull():
            return QPoint(0, 0)
            
        # Get the displayed pixmap
        displayed_pixmap = super().pixmap()
        if not displayed_pixmap or displayed_pixmap.isNull():
            return QPoint(0, 0)
            
        # Calculate scaling factors
        x_scale = self._pixmap.width() / displayed_pixmap.width()
        y_scale = self._pixmap.height() / displayed_pixmap.height()
        
        # Calculate offset (for centered image)
        x_offset = (self.width() - displayed_pixmap.width()) // 2
        y_offset = (self.height() - displayed_pixmap.height()) // 2
        
        # Map position
        img_x = int((pos.x() - x_offset) * x_scale)
        img_y = int((pos.y() - y_offset) * y_scale)
        
        return QPoint(img_x, img_y)
        
    def _highlight_region(self, pos, color):
        """Highlight a region with similar color."""
        if not self._pixmap or self._pixmap.isNull():
            return
            
        # For actual processing, use a more sophisticated approach with floodfill
        try:
            # Create a copy of the image for flood fill
            img = self._pixmap.toImage()
            width = img.width()
            height = img.height()
            
            # Get the color at the position
            target_color = img.pixelColor(pos)
            r, g, b, a = target_color.red(), target_color.green(), target_color.blue(), target_color.alpha()
            
            # Create a mask for flood fill
            mask = np.zeros((height + 2, width + 2), dtype=np.uint8)
            
            # Convert image to numpy array for OpenCV
            ptr = img.constBits()
            ptr.setsize(img.bytesPerLine() * height)
            img_array = np.array(ptr).reshape(height, width, 4)
            
            # Convert to BGR for OpenCV
            bgr_img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            
            # Flood fill parameters - use lower tolerance for more precise background detection
            flags = 4  # 4-connected
            tolerance = 10  # Lower color tolerance for better precision
            
            # Perform flood fill
            if 0 <= pos.y() < height and 0 <= pos.x() < width:
                cv2.floodFill(
                    bgr_img, mask, (pos.x(), pos.y()), 
                    (255, 0, 0),  # Fill color (doesn't matter)
                    (tolerance, tolerance, tolerance),  # Lower diff
                    (tolerance, tolerance, tolerance),  # Upper diff
                    flags
                )
                
                # The mask now contains the filled region (with a 1-pixel border)
                # Extract the actual mask (without the border)
                fill_mask = mask[1:-1, 1:-1]
                
                # Store the mask for removal
                self._current_mask = fill_mask
                
                # Find contours in the mask
                contours, _ = cv2.findContours(fill_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Get the largest contour
                    largest_contour = max(contours, key=cv2.contourArea)
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    self._highlight_rect = QRect(x, y, w, h)
                    
                    # Create a preview of what will be removed
                    preview_pixmap = QPixmap(self._pixmap)
                    painter = QPainter(preview_pixmap)
                    painter.setOpacity(0.5)  # Semi-transparent
                    painter.fillRect(x, y, w, h, QColor(0, 255, 255))  # Cyan highlight
                    painter.end()
                    
                    # Store the preview
                    self._preview_pixmap = preview_pixmap
                    
                    # Update the display with the preview
                    super().setPixmap(preview_pixmap)
                    return
        except Exception as e:
            print(f"Error in highlight_region: {e}")
            
        # Fall back to simple rectangle if flood fill fails
        self._highlight_rect = QRect(pos.x() - 30, pos.y() - 30, 60, 60)
        
        # Emit signal with detected region
        self.hover_region_detected.emit(self._highlight_rect)
        
    def _remove_region(self, pos):
        """Remove a region with similar color."""
        if not self._pixmap or not self._mask:
            return
            
        # If we have a current mask from auto-detection, use it
        if hasattr(self, '_current_mask') and self._current_mask is not None:
            # Ask user to confirm removal
            reply = QMessageBox.question(None, "Remove Background", 
                                        "Remove the highlighted area?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                # Create painter for the mask
                painter = QPainter(self._mask)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Set up the brush
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0))  # Black = transparent
                
                # Convert numpy mask to QImage
                mask_height, mask_width = self._current_mask.shape
                mask_image = QImage(self._current_mask.data, mask_width, mask_height, mask_width, QImage.Format.Format_Grayscale8)
                
                # Draw the mask
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(0, 0, mask_image)
                painter.end()
                
                # Apply the updated mask to the working pixmap
                self._update_working_pixmap()
            else:
                # Restore original display
                if hasattr(self, '_working_pixmap') and self._working_pixmap:
                    super().setPixmap(self._working_pixmap)
            
            # Clear the current mask and preview
            self._current_mask = None
            if hasattr(self, '_preview_pixmap'):
                delattr(self, '_preview_pixmap')
        else:
            # Fallback to simple circle removal
            painter = QPainter(self._mask)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Set up the brush
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0))  # Black = transparent
            
            # Draw circle at position with larger radius for region removal
            radius = self._brush_size * 2
            painter.drawEllipse(pos, radius, radius)
            painter.end()
            
            # Apply the updated mask to the working pixmap
            self._update_working_pixmap()

class SpriteCraftEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpriteCraft Editor")
        self.setGeometry(100, 100, 1280, 900)  # Wider window for better layout

        self.palette_editor = PaletteEditor()
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_plugins()
        self.image_processor = ImageProcessor()
        self.sprite_sheet_generator = SpriteSheetGenerator()
        
        # Tool settings
        self.brush_size = 20
        self.brush_hardness = 0.5
        
        # Animation frames
        self.frames = []
        self.current_frame = 0
        
        # Set up keyboard shortcuts
        self.setup_shortcuts()

        # Set modern dark theme style
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #f0f0f0;
            }
            QLabel, QMenu, QMenuBar {
                background-color: transparent;
                color: #f0f0f0;
            }
            QToolBar {
                background-color: #252526;
                border: none;
                spacing: 3px;
                padding: 2px;
            }
            QToolButton {
                background-color: #2d2d30;
                border: none;
                border-radius: 4px;
                padding: 6px;
                margin: 2px;
                color: #f0f0f0;
            }
            QToolButton:hover {
                background-color: #3e3e42;
            }
            QToolButton:pressed {
                background-color: #007acc;
            }
            QPushButton {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 6px 12px;
                color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #3e3e42;
                border-color: #007acc;
            }
            QPushButton:pressed {
                background-color: #007acc;
            }
            QSlider::groove:horizontal {
                border: 1px solid #3e3e42;
                height: 6px;
                background: #2d2d30;
                margin: 2px 0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #007acc;
                border: none;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QDockWidget {
                titlebar-close-icon: url(close.png);
                titlebar-normal-icon: url(undock.png);
            }
            QDockWidget::title {
                background-color: #252526;
                padding-left: 10px;
                padding-top: 4px;
                border-bottom: 1px solid #3e3e42;
            }
            QGroupBox {
                border: 1px solid #3e3e42;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: #007acc;
            }
            QFrame {
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                border: none;
                background: #2d2d30;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3e3e42;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.init_ui()
        self.canvas.cropping_finished.connect(self.perform_crop)
        self.canvas.image_updated.connect(self.update_preview)
        
        # Set up keyboard shortcuts
        self.setup_shortcuts()

    def init_ui(self):
        # Create main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Create a splitter for main area and preview
        self.main_area = QWidget()
        self.main_area_layout = QVBoxLayout(self.main_area)
        
        # Create status bar for messages
        self.statusBar().showMessage("Ready", 3000)
        
        # Add UI customization menu
        self.create_ui_customization_menu()
        self.main_area_layout.setContentsMargins(8, 8, 8, 8)
        
        # Create canvas for image editing with pixel grid
        self.canvas = EditableLabel(self)  # Using EditableLabel instead of QLabel here
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(800, 600)
        self.canvas.setStyleSheet("QLabel { background-color: #1a1a1a; color: white; border: 1px solid #3e3e42; }")
        
        # Create canvas container with toolbar
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        
        # Canvas toolbar
        canvas_toolbar = QWidget()
        canvas_toolbar.setFixedHeight(36)
        canvas_toolbar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e42;")
        canvas_toolbar_layout = QHBoxLayout(canvas_toolbar)
        canvas_toolbar_layout.setContentsMargins(8, 0, 8, 0)
        
        # Zoom controls
        zoom_label = QLabel("Zoom:")
        canvas_toolbar_layout.addWidget(zoom_label)
        
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.clicked.connect(lambda: self.zoom_image(0.8))
        canvas_toolbar_layout.addWidget(zoom_out_btn)
        
        # Editable zoom value
        self.zoom_input = QLineEdit("100%")
        self.zoom_input.setFixedWidth(60)
        self.zoom_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_input.returnPressed.connect(self.apply_zoom_from_input)
        canvas_toolbar_layout.addWidget(self.zoom_input)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.clicked.connect(lambda: self.zoom_image(1.25))
        canvas_toolbar_layout.addWidget(zoom_in_btn)
        
        # Grid toggle
        canvas_toolbar_layout.addStretch()
        
        grid_btn = QPushButton("Grid")
        grid_btn.setCheckable(True)
        canvas_toolbar_layout.addWidget(grid_btn)
        
        # Add components to canvas container
        canvas_layout.addWidget(canvas_toolbar)
        canvas_layout.addWidget(self.canvas, 1)
        
        # Add canvas container to main layout
        self.main_area_layout.addWidget(canvas_container, 4)
        
        # Create preview area with animation frames
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_frame.setStyleSheet("QFrame { background-color: #252526; border: 1px solid #3e3e42; }")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        
        # Preview header with title
        preview_header = QWidget()
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_title = QLabel("Animation Preview")
        preview_title.setStyleSheet("QLabel { color: #007acc; font-weight: bold; }")
        preview_header_layout.addWidget(preview_title)
        
        # Add animation controls
        preview_header_layout.addStretch()
        
        # Preview image
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(200, 150)
        self.preview_label.setStyleSheet("QLabel { background-color: #1a1a1a; border-radius: 4px; }")
        self.preview_label.setText("No preview available")
        
        # Add components to preview layout
        preview_layout.addWidget(preview_header)
        preview_layout.addWidget(self.preview_label, 1)
        
        # Add preview to main area layout
        self.main_area_layout.addWidget(preview_frame, 1)
        
        # Add main area to main layout
        self.main_layout.addWidget(self.main_area, 4)
        
        # Create tools panel as a dock widget
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                                   QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.tools_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | 
                                       Qt.DockWidgetArea.RightDockWidgetArea)
        
        # Create tools panel content
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setContentsMargins(8, 12, 8, 8)
        tools_layout.setSpacing(10)
        
        # Drawing tools group
        drawing_group = QGroupBox("Pixel Art Tools")
        drawing_layout = QVBoxLayout(drawing_group)
        drawing_layout.setSpacing(6)
        
        # Drawing tools buttons
        pencil_btn = QPushButton("🖊️ Pencil")
        pencil_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        pencil_btn.clicked.connect(self.enable_pencil_tool)
        drawing_layout.addWidget(pencil_btn)
        
        eraser_btn = QPushButton("🧽 Eraser")
        eraser_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        eraser_btn.clicked.connect(self.enable_eraser_tool)
        drawing_layout.addWidget(eraser_btn)
        
        fill_btn = QPushButton("🪣 Fill")
        fill_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        fill_btn.clicked.connect(self.enable_fill_tool)
        drawing_layout.addWidget(fill_btn)
        
        # Add drawing group to tools layout
        tools_layout.addWidget(drawing_group)
        
        # Background removal tools group
        bg_group = QGroupBox("Background Removal")
        bg_layout = QVBoxLayout(bg_group)
        bg_layout.setSpacing(6)
        
        # Auto detect button
        auto_detect_btn = QPushButton("🔍 Auto Detect")
        auto_detect_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        auto_detect_btn.clicked.connect(self.enable_auto_detect)
        bg_layout.addWidget(auto_detect_btn)
        
        # Brush tool button
        brush_btn = QPushButton("🖌️ Magic Brush")
        brush_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        brush_btn.clicked.connect(self.enable_brush_tool)
        bg_layout.addWidget(brush_btn)
        
        # Brush size controls
        brush_size_widget = QWidget()
        brush_size_layout = QHBoxLayout(brush_size_widget)
        brush_size_layout.setContentsMargins(0, 0, 0, 0)
        
        brush_size_label = QLabel("Size:")
        brush_size_layout.addWidget(brush_size_label)
        
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setRange(5, 50)
        self.brush_size_slider.setValue(self.brush_size)
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)
        brush_size_layout.addWidget(self.brush_size_slider)
        
        self.brush_size_value = QLabel(f"{self.brush_size}")
        brush_size_layout.addWidget(self.brush_size_value)
        
        bg_layout.addWidget(brush_size_widget)
        
        # Reset button
        reset_btn = QPushButton("↺ Reset Image")
        reset_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        reset_btn.clicked.connect(self.reset_image)
        bg_layout.addWidget(reset_btn)
        
        # Add background group to tools layout
        tools_layout.addWidget(bg_group)
        
        # Animation tools group
        anim_group = QGroupBox("Animation")
        anim_layout = QVBoxLayout(anim_group)
        anim_layout.setSpacing(6)
        
        # Frame controls
        add_frame_btn = QPushButton("➕ Add Frame")
        add_frame_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        anim_layout.addWidget(add_frame_btn)
        
        duplicate_frame_btn = QPushButton("📋 Duplicate Frame")
        duplicate_frame_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        anim_layout.addWidget(duplicate_frame_btn)
        
        # Add animation group to tools layout
        tools_layout.addWidget(anim_group)
        
        # Add spacer to push everything to the top
        tools_layout.addStretch()
        
        # Set the tools widget as the dock content
        self.tools_dock.setWidget(tools_widget)
        
        # Add dock to main window
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.tools_dock)
        
        # Create color palette panel
        palette_dock = QDockWidget("Color Palette", self)
        palette_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                               QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        palette_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | 
                                   Qt.DockWidgetArea.RightDockWidgetArea |
                                   Qt.DockWidgetArea.BottomDockWidgetArea)
        
        # Create palette content
        palette_widget = QWidget()
        palette_layout = QVBoxLayout(palette_widget)
        palette_layout.setContentsMargins(8, 8, 8, 8)
        
        # Color grid
        color_grid = QWidget()
        color_grid_layout = QGridLayout(color_grid)
        color_grid_layout.setSpacing(2)
        color_grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add some default colors
        default_colors = [
            "#FF0000", "#FF8000", "#FFFF00", "#80FF00", "#00FF00", "#00FF80", 
            "#00FFFF", "#0080FF", "#0000FF", "#8000FF", "#FF00FF", "#FF0080",
            "#FFFFFF", "#D0D0D0", "#909090", "#404040", "#000000", "#FF8080",
            "#FFD080", "#FFFF80", "#D0FF80", "#80FF80", "#80FFD0", "#80FFFF"
        ]
        
        # Create color swatches
        row, col = 0, 0
        for color in default_colors:
            swatch = QFrame()
            swatch.setStyleSheet(f"background-color: {color}; border: 1px solid #3e3e42;")
            swatch.setFixedSize(24, 24)
            color_grid_layout.addWidget(swatch, row, col)
            col += 1
            if col > 5:
                col = 0
                row += 1
        
        # Add color picker button
        color_picker_btn = QPushButton("+ Add Color")
        
        # Add components to palette layout
        palette_layout.addWidget(color_grid)
        palette_layout.addWidget(color_picker_btn)
        palette_layout.addStretch()
        
        # Set the palette widget as the dock content
        palette_dock.setWidget(palette_widget)
        
        # Add palette dock to main window
        self.palette_dock = palette_dock
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, palette_dock)
        
        # Create menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_image)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        crop_action = QAction("Crop", self)
        crop_action.triggered.connect(self.crop_image)
        edit_menu.addAction(crop_action)
        
        # Background removal submenu
        bg_menu = edit_menu.addMenu("Background Removal")
        
        auto_bg_action = QAction("Auto Remove Background", self)
        auto_bg_action.triggered.connect(self.remove_background)
        bg_menu.addAction(auto_bg_action)
        
        brush_bg_action = QAction("Brush Tool", self)
        brush_bg_action.triggered.connect(self.enable_brush_tool)
        bg_menu.addAction(brush_bg_action)
        
        reset_bg_action = QAction("Reset Image", self)
        reset_bg_action.triggered.connect(self.reset_image)
        edit_menu.addAction(reset_bg_action)
        
        # Export menu
        export_menu = menubar.addMenu("Export")
        
        sheet_action = QAction("Export Sprite Sheet", self)
        sheet_action.triggered.connect(self.export_sprite_sheet)
        export_menu.addAction(sheet_action)
        
        # Create toolbar
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setObjectName("Main Toolbar")  # Set object name for finding it later
        toolbar.addAction(open_action)
        toolbar.addAction(save_action)
        toolbar.addSeparator()
        toolbar.addAction(crop_action)
        toolbar.addAction(auto_bg_action)
        toolbar.addAction(brush_bg_action)
        toolbar.addSeparator()
        toolbar.addAction(sheet_action)
        
        # Create brush settings toolbar
        brush_toolbar = self.addToolBar("Brush Settings")
        
        # Brush size label
        brush_size_label = QLabel("Brush Size: ")
        brush_size_label.setStyleSheet("color: white; margin-left: 10px;")
        brush_toolbar.addWidget(brush_size_label)
        
        # Brush size slider
        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setRange(5, 50)
        self.brush_size_slider.setValue(self.brush_size)
        self.brush_size_slider.setFixedWidth(100)
        self.brush_size_slider.valueChanged.connect(self.update_brush_size)
        brush_toolbar.addWidget(self.brush_size_slider)

    def open_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp);;All Files (*)")
        if file_name:
            try:
                image = QImage(file_name)
                if image.isNull():
                    QMessageBox.warning(self, "Loading Error", "Could not open file.")
                    return
                pixmap = QPixmap.fromImage(image)
                self.canvas.setPixmap(pixmap)  # Using setPixmap on EditableLabel instance
                self.update_preview()  # Update the preview
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open image: {str(e)}")

    def save_image(self):
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image to save!")
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "PNG (*.png);;JPEG (*.jpg);;All Files (*.*)")
        if file_name:
            try:
                self.canvas.pixmap().save(file_name)
                QMessageBox.information(self, "Success", f"Image saved to {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save image: {str(e)}")

    def show_color_picker(self):
        color = QColorDialog.getColor()
        if color.isValid():
            print(color.name())

    def crop_image(self):
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded to crop!")
            return
        
        self.canvas.set_mode(EditableLabel.MODE_CROP)
        QMessageBox.information(self, "Crop Tool", "Click and drag to select the area to crop, then release to apply.")

    def remove_background(self):
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return

        try:
            # Show processing message
            QMessageBox.information(self, "Processing", "Removing background... This may take a moment.")
            
            # Get the image from the canvas
            pixmap = self.canvas.pixmap()
            qimage = pixmap.toImage()

            # Convert to RGBA format if needed
            if qimage.format() != QImage.Format.Format_RGBA8888:
                qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)

            # Convert QImage to numpy array
            width = qimage.width()
            height = qimage.height()
            ptr = qimage.constBits()
            ptr.setsize(qimage.bytesPerLine() * height)
            
            # Reshape array to correct dimensions
            image_array = np.array(ptr).reshape(height, width, 4)
            
            # Process the image with more conservative settings
            processed_image_array = self.image_processor.remove_background(image_array, conservative=True)

            if processed_image_array is not None:
                # Convert back to QImage
                height, width, channel = processed_image_array.shape
                bytes_per_line = 4 * width
                
                # Create QImage from the processed array
                processed_qimage = QImage(
                    processed_image_array.data, 
                    width, 
                    height, 
                    bytes_per_line, 
                    QImage.Format.Format_RGBA8888
                )
                
                # Convert to pixmap
                processed_pixmap = QPixmap.fromImage(processed_qimage)
                
                # Show preview with option to accept or reject
                preview_dialog = QMessageBox(self)
                preview_dialog.setWindowTitle("Background Removal Preview")
                preview_dialog.setText("How does this look?")
                preview_dialog.setStandardButtons(
                    QMessageBox.StandardButton.Apply | 
                    QMessageBox.StandardButton.Cancel
                )
                preview_dialog.setDefaultButton(QMessageBox.StandardButton.Apply)
                
                # Set the preview image
                preview_label = QLabel()
                preview_label.setPixmap(processed_pixmap.scaled(
                    400, 300, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                preview_dialog.layout().addWidget(preview_label, 1, 0, 1, preview_dialog.layout().columnCount())
                
                # Show the dialog
                if preview_dialog.exec() == QMessageBox.StandardButton.Apply:
                    # Store the processed pixmap as both original and working pixmap
                    self.canvas._pixmap = QPixmap(processed_pixmap)
                    self.canvas._working_pixmap = QPixmap(processed_pixmap)
                    self.canvas._unzoomed_pixmap = QPixmap(processed_pixmap)
                    
                    # Apply current zoom level
                    zoom_level = getattr(self.canvas, '_zoom_level', 0.5)
                    scaled_pixmap = processed_pixmap.scaled(
                        int(processed_pixmap.width() * zoom_level),
                        int(processed_pixmap.height() * zoom_level),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    # Update the display
                    super(EditableLabel, self.canvas).setPixmap(scaled_pixmap)
                    
                    # Update zoom display
                    if hasattr(self, 'zoom_input'):
                        self.zoom_input.setText(f"{int(zoom_level * 100)}%")
                        
                    # Update preview
                    self.update_preview()
                    
                    QMessageBox.information(self, "Success", "Background removed.")
                else:
                    QMessageBox.information(self, "Cancelled", "Background removal cancelled.")
            else:
                QMessageBox.warning(self, "Warning", "Background removal failed.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred during background removal: {str(e)}")

    def perform_crop(self, crop_rect):
        if self.canvas.pixmap():
            orig_pixmap = self.canvas.pixmap()
            if crop_rect.width() <= 0 or crop_rect.height() <= 0:
                QMessageBox.warning(self, "Warning", "Crop area is invalid!")
                return
                
            cropped_pixmap = orig_pixmap.copy(crop_rect)
            if not cropped_pixmap.isNull():
                self.canvas.setPixmap(cropped_pixmap)
            else:
                QMessageBox.warning(self, "Warning", "Crop area is invalid!")
    
    def export_sprite_sheet(self):
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image to export as sprite sheet!")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sprite Sheet",
            "",
            "PNG (*.png);;All Files (*.*)"
        )
        if file_name:
            try:
                pixmap = self.canvas.pixmap()
                qimage = pixmap.toImage()

                if qimage.format() != QImage.Format.Format_RGBA8888:
                    qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)

                buffer = QBuffer()
                buffer.open(QBuffer.OpenModeFlag.ReadWrite)
                qimage.save(buffer, "PNG")
                buffer.seek(0)  # Reset buffer position to start
                pil_image = Image.open(io.BytesIO(buffer.data()))

                self.sprite_sheet_generator.clear_images()
                self.sprite_sheet_generator.add_image(pil_image)

                metadata_file_name = file_name.replace(".png", ".json") if file_name.lower().endswith(".png") else file_name + ".json"

                self.sprite_sheet_generator.save_sheet(file_name, metadata_file_name)

                QMessageBox.information(self, "Success", f"Sprite sheet saved to {file_name} and metadata to {metadata_file_name}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred during sprite sheet export: {str(e)}")
    
    def enable_brush_tool(self):
        """Enable the brush tool for manual background removal."""
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
            
        self.canvas.set_mode(EditableLabel.MODE_BRUSH)
        self.canvas.set_brush_size(self.brush_size)
        QMessageBox.information(self, "Brush Tool", 
                               "Use the brush to erase parts of the image.\n"
                               "Adjust brush size using the slider in the toolbar.")
    
    def update_brush_size(self, size):
        """Update the brush size from the slider."""
        self.brush_size = size
        if self.canvas:
            self.canvas.set_brush_size(size)
        if hasattr(self, 'brush_size_value'):
            self.brush_size_value.setText(f"{size}")
    
    def enable_auto_detect(self):
        """Enable the auto-detect tool for background removal."""
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
            
        self.canvas.set_mode(EditableLabel.MODE_AUTO_DETECT)
        QMessageBox.information(self, "Auto Detect Tool", 
                               "Hover over background areas to detect regions.\n"
                               "Click to remove the detected region.\n"
                               "Use the brush tool for fine-tuning.")
    
    def reset_image(self):
        """Reset the image to its original state."""
        if not self.canvas.original_pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
            
        reply = QMessageBox.question(self, "Reset Image", 
                                    "Are you sure you want to reset the image to its original state?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            # Create a new copy of the original pixmap to avoid reference issues
            original = QPixmap(self.canvas.original_pixmap())
            
            # Reset all editing state
            self.canvas._working_pixmap = QPixmap(original)
            if hasattr(self.canvas, '_mask'):
                # Reset the mask to fully opaque
                self.canvas._mask = QImage(original.size(), QImage.Format.Format_Alpha8)
                self.canvas._mask.fill(255)  # 255 = fully opaque
            
            # Reset zoom level
            if hasattr(self.canvas, '_zoom_level'):
                self.canvas._zoom_level = 1.0
                if hasattr(self, 'zoom_input'):
                    self.zoom_input.setText("100%")
            
            # Clear any stored unzoomed pixmap
            if hasattr(self.canvas, '_unzoomed_pixmap'):
                delattr(self.canvas, '_unzoomed_pixmap')
                
            # Set the pixmap and update mode
            self.canvas.setPixmap(original)
            self.canvas.set_mode(EditableLabel.MODE_NONE)
            self.update_preview()
            
    def enable_pencil_tool(self):
        """Enable the pencil tool for pixel drawing."""
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
            
        self.canvas.set_mode(EditableLabel.MODE_PENCIL)
        self.canvas.set_brush_size(1)  # Default to 1px for pixel art
        QMessageBox.information(self, "Pencil Tool", "Click and drag to draw pixels.")
        
    def enable_eraser_tool(self):
        """Enable the eraser tool for pixel erasing."""
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
            
        self.canvas.set_mode(EditableLabel.MODE_ERASER)
        self.canvas.set_brush_size(self.brush_size)
        QMessageBox.information(self, "Eraser Tool", "Click and drag to erase pixels.")
        
    def enable_fill_tool(self):
        """Enable the fill tool for filling areas."""
        if not self.canvas.pixmap():
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
            
        self.canvas.set_mode(EditableLabel.MODE_FILL)
        QMessageBox.information(self, "Fill Tool", "Click an area to fill it with the selected color.")
    
    def zoom_image(self, factor):
        """Zoom the image by a factor or to a specific percentage."""
        if not self.canvas.pixmap():
            return
            
        # Initialize zoom level if not set
        if not hasattr(self.canvas, '_zoom_level'):
            self.canvas._zoom_level = 1.0
            
        # If factor is a number, use it as a multiplier
        if isinstance(factor, (int, float)):
            self.canvas._zoom_level *= factor
        # If factor is a string (from input), parse it as a percentage
        elif isinstance(factor, str):
            try:
                # Remove % sign if present and convert to float
                percentage = float(factor.replace('%', ''))
                self.canvas._zoom_level = percentage / 100.0
            except ValueError:
                return
                
        # Limit zoom range
        self.canvas._zoom_level = max(0.1, min(5.0, self.canvas._zoom_level))
        
        # Update zoom display
        if hasattr(self, 'zoom_input'):
            self.zoom_input.setText(f"{int(self.canvas._zoom_level * 100)}%")
        
        # Get current working pixmap (not original)
        current = self.canvas.pixmap()
        if not current:
            return
            
        # Store current working pixmap if not already stored
        if not hasattr(self.canvas, '_unzoomed_pixmap'):
            self.canvas._unzoomed_pixmap = QPixmap(current)
        
        # Calculate new size
        new_width = int(self.canvas._unzoomed_pixmap.width() * self.canvas._zoom_level)
        new_height = int(self.canvas._unzoomed_pixmap.height() * self.canvas._zoom_level)
        
        # Scale the pixmap
        scaled = self.canvas._unzoomed_pixmap.scaled(
            new_width, 
            new_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Update the canvas without changing the stored pixmap
        super(EditableLabel, self.canvas).setPixmap(scaled)
        self.update_preview()
    
    def apply_zoom_from_input(self):
        """Apply zoom from the input field."""
        if hasattr(self, 'zoom_input'):
            zoom_text = self.zoom_input.text()
            # Make sure the text has a % sign
            if not zoom_text.endswith('%'):
                zoom_text += '%'
                self.zoom_input.setText(zoom_text)
            # Apply the zoom
            self.zoom_image(zoom_text)
    
    def create_ui_customization_menu(self):
        """Create a menu for UI customization."""
        # Create View menu
        view_menu = self.menuBar().addMenu("View")
        
        # Dock widgets visibility submenu
        docks_menu = view_menu.addMenu("Panels")
        
        # Add actions for each dock widget
        tools_dock_action = QAction("Tools Panel", self)
        tools_dock_action.setCheckable(True)
        tools_dock_action.setChecked(True)
        tools_dock_action.triggered.connect(lambda checked: self.tools_dock.setVisible(checked))
        docks_menu.addAction(tools_dock_action)
        
        # Add action for palette dock
        palette_dock_action = QAction("Color Palette", self)
        palette_dock_action.setCheckable(True)
        palette_dock_action.setChecked(True)
        palette_dock_action.triggered.connect(lambda checked: self.palette_dock.setVisible(checked))
        docks_menu.addAction(palette_dock_action)
        
        # Layout options
        layout_menu = view_menu.addMenu("Layout")
        
        # Reset layout
        reset_layout_action = QAction("Reset Layout", self)
        reset_layout_action.triggered.connect(self.reset_layout)
        layout_menu.addAction(reset_layout_action)
        
        # Default zoom
        default_zoom_menu = view_menu.addMenu("Default Zoom")
        
        zoom_options = [("25%", 0.25), ("50%", 0.5), ("75%", 0.75), ("100%", 1.0), ("150%", 1.5), ("200%", 2.0)]
        for label, factor in zoom_options:
            zoom_action = QAction(label, self)
            zoom_action.triggered.connect(lambda checked, f=factor: self.set_default_zoom(f))
            default_zoom_menu.addAction(zoom_action)
            
    def setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Create Edit menu if it doesn't exist
        edit_menu = None
        for action in self.menuBar().actions():
            if action.text() == "Edit":
                edit_menu = action.menu()
                break
                
        if not edit_menu:
            edit_menu = self.menuBar().addMenu("Edit")
        
        # Add separator before undo/redo
        edit_menu.addSeparator()
        
        # Add undo action with icon
        self.undo_action_obj = QAction("Undo", self)
        self.undo_action_obj.setShortcut("Ctrl+Z")
        self.undo_action_obj.triggered.connect(self.undo_action)
        edit_menu.addAction(self.undo_action_obj)
        
        # Add redo action with icon
        self.redo_action_obj = QAction("Redo", self)
        self.redo_action_obj.setShortcut("Ctrl+Y")
        self.redo_action_obj.triggered.connect(self.redo_action)
        edit_menu.addAction(self.redo_action_obj)
        
        # Add to toolbar
        toolbar = self.findChild(QToolBar, "Main Toolbar")
        if toolbar:
            toolbar.addSeparator()
            toolbar.addAction(self.undo_action_obj)
            toolbar.addAction(self.redo_action_obj)
    
    def undo_action(self):
        """Handle undo action."""
        if hasattr(self.canvas, 'undo'):
            if self.canvas.undo():
                self.update_preview()
                self.statusBar().showMessage("Undo", 2000)
            else:
                self.statusBar().showMessage("Nothing to undo", 2000)
    
    def redo_action(self):
        """Handle redo action."""
        if hasattr(self.canvas, 'redo'):
            if self.canvas.redo():
                self.update_preview()
                self.statusBar().showMessage("Redo", 2000)
            else:
                self.statusBar().showMessage("Nothing to redo", 2000)
    
    def reset_layout(self):
        """Reset the UI layout to default."""
        # Reset dock widget positions
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.tools_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.palette_dock)
        
        # Show all dock widgets
        self.tools_dock.setVisible(True)
        self.palette_dock.setVisible(True)
        
        # Reset main layout
        self.main_layout.setStretch(0, 4)  # Canvas area
        self.main_layout.setStretch(1, 1)  # Tools area
        
    def set_default_zoom(self, factor):
        """Set the default zoom level."""
        self.default_zoom = factor
        
        # Apply to current image if one is loaded
        if hasattr(self.canvas, '_pixmap') and self.canvas._pixmap:
            self.canvas._zoom_level = factor
            
            # Update zoom display
            if hasattr(self, 'zoom_input'):
                self.zoom_input.setText(f"{int(factor * 100)}%")
            
            # Apply zoom
            self.zoom_image(1.0)  # Apply with factor 1.0 to use the current zoom level
    
    def update_preview(self):
        """Update the preview image."""
        if not self.canvas.pixmap() or not hasattr(self, 'preview_label'):
            return
            
        # Create a scaled version of the working pixmap for the preview
        preview_size = self.preview_label.size()
        scaled_preview = self.canvas.pixmap().scaled(
            preview_size, 
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled_preview)

def main():
    app = QApplication(sys.argv)
    main_window = SpriteCraftEditor()
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()