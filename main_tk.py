import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import io
import os
from image_processor import ImageProcessor
import threading
import queue
from tkinter import PhotoImage
from pathlib import Path

class ImageProcessor:
    """Class to handle image processing tasks"""
    def __init__(self):
        pass
    
    def remove_background(self, image_array):
        """Remove background from image using OpenCV"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, 5)
            
            # Thresholding
            _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Create mask for the largest contour
            mask = np.zeros_like(image_array)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                cv2.drawContours(mask, [largest_contour], -1, (255), thickness=cv2.FILLED)
            
            # Convert mask to 3 channels
            mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            
            # Bitwise and to remove background
            result = cv2.bitwise_and(image_array, mask)
            
            return result
        except Exception as e:
            print(f"Error in remove_background: {str(e)}")
            return None

class SpriteCraftEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("SpriteCraft Editor")
        self.geometry("1200x800")
        
        # Initialize image processor
        self.image_processor = ImageProcessor()
        
        # Configure window to be centered
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 1200) // 2
        y = (screen_height - 800) // 2
        self.geometry(f"1200x800+{x}+{y}")
        
        # Configure grid
        self.grid_columnconfigure(1, weight=3)  # Main canvas gets more space
        self.grid_columnconfigure(0, weight=1)  # Left panel
        self.grid_columnconfigure(2, weight=1)  # Right panel
        self.grid_rowconfigure(0, weight=1)

        # Set minimum window size
        self.minsize(800, 600)
        
        # Set dark theme
        self.configure(bg='#2b2b2b')
        self.style = ttk.Style()
        self.style.theme_use('clam')  # Use clam theme as base
        self.style.configure('.', background='#2b2b2b', foreground='white')
        self.style.configure('TFrame', background='#2b2b2b')
        self.style.configure('TLabel', background='#2b2b2b', foreground='white')
        self.style.configure('TButton', background='#3b3b3b', foreground='white')

        # Create main container
        self.main_container = ttk.Frame(self, style='Dark.TFrame')
        self.main_container.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        self.main_container.grid_columnconfigure(1, weight=3)
        self.main_container.grid_rowconfigure(0, weight=1)
        
        # Initialize variables
        self.current_image = None
        self.current_tool = None
        self.palette_colors = []
        self.last_canvas_size = None
        
        # Create panels
        self.create_left_panel()
        self.create_main_canvas()
        self.create_right_panel()
        
        # Create menu bar
        self.create_menu()
        
        # Bind resize event
        self.bind('<Configure>', self.on_window_resize)
        
    def create_menu(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open", command=self.open_image)
        file_menu.add_command(label="Save", command=self.save_image)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Crop", command=self.crop_image)
        edit_menu.add_command(label="Remove Background", command=self.remove_background)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Reset Zoom", command=lambda: None)
        
    def create_left_panel(self):
        """Create the left panel with tools"""
        left_frame = ttk.Frame(self.main_container, padding="5")
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
          # Tools label
        tools_label = ttk.Label(left_frame, text="Tools")
        tools_label.pack(pady=(0, 10))
        
        # Tool buttons with icons (using text for now)
        tools = [
            ("🖼 Open", self.open_image),
            ("💾 Save", self.save_image),
            ("✂️ Crop", self.crop_image),
            ("🎭 Remove BG", self.remove_background),
            ("📑 Export", self.export_sprite_sheet)
        ]
        
        buttons_frame = ttk.Frame(left_frame)
        buttons_frame.pack(fill=tk.X, expand=True)
        
        for name, command in tools:
            btn = ttk.Button(buttons_frame, text=name, command=command)
            btn.pack(pady=2, fill=tk.X)
        
    def create_main_canvas(self):
        """Create the main canvas for image editing"""
        # Main frame for canvas and controls
        canvas_frame = ttk.Frame(self.main_container)
        canvas_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        canvas_frame.grid_rowconfigure(1, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Zoom controls
        zoom_frame = ttk.Frame(canvas_frame)
        zoom_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        ttk.Label(zoom_frame, text="Zoom:").pack(side=tk.LEFT, padx=5)
        
        zoom_out = ttk.Button(zoom_frame, text="➖", width=3, command=lambda: self.zoom_image(0.9))
        zoom_out.pack(side=tk.LEFT, padx=2)
        
        self.zoom_label = ttk.Label(zoom_frame, text="100%", width=8)
        self.zoom_label.pack(side=tk.LEFT, padx=2)
        
        zoom_in = ttk.Button(zoom_frame, text="➕", width=3, command=lambda: self.zoom_image(1.1))
        zoom_in.pack(side=tk.LEFT, padx=2)
        
        fit_button = ttk.Button(zoom_frame, text="Fit", width=6, command=self.fit_image)
        fit_button.pack(side=tk.LEFT, padx=5)
        
        # Canvas with dark background
        canvas_container = ttk.Frame(canvas_frame)
        canvas_container.grid(row=1, column=0, sticky="nsew")
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(
            canvas_container,
            bg="#1b1b1b",
            highlightthickness=0,
            scrollregion=(0, 0, 800, 600)
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbars
        x_scroll = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        
        # Mouse wheel zoom
        self.canvas.bind("<Control-MouseWheel>", self.mouse_wheel_zoom)
        
        # Welcome message
        self.canvas.create_text(
            400, 300,
            text="Welcome to SpriteCraft Editor\nDrag and drop or open an image to begin",
            fill="white",
            font=("Arial", 14),
            justify=tk.CENTER,
            tags="welcome"
        )
        
        # Initialize zoom level
        self.zoom_level = 1.0
        
    def create_right_panel(self):
        """Create the right panel with palette"""
        # Create main frame
        right_frame = ttk.Frame(self.main_container, padding="5")
        right_frame.grid(row=0, column=2, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Add separator between main canvas and right panel
        separator = ttk.Separator(self.main_container, orient="vertical")
        separator.grid(row=0, column=1, sticky="ns", padx=5)
        
        # Header
        header_frame = ttk.Frame(right_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Color Palette").pack(side=tk.LEFT)
        
        # Palette grid
        self.palette_frame = ttk.Frame(right_frame)
        self.palette_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Configure grid columns
        for i in range(4):
            self.palette_frame.grid_columnconfigure(i, weight=1)
        
        # Controls section
        controls_frame = ttk.Frame(right_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        # Control buttons
        buttons = [
            ("➕ Add", self.add_color),
            ("🎨 Extract", self.extract_colors),
            ("🗑 Clear", lambda: (self.palette_colors.clear(), self.update_palette_view()))
        ]
        
        # Create button container with grid layout
        button_grid = ttk.Frame(controls_frame)
        button_grid.pack(fill=tk.X)
        button_grid.grid_columnconfigure(0, weight=1)
        button_grid.grid_columnconfigure(1, weight=1)
        
        # Add buttons to grid
        for i, (text, command) in enumerate(buttons):
            row = i // 2
            col = i % 2
            btn = ttk.Button(button_grid, text=text, command=command)
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
        
    def open_image(self):
        """Open an image file"""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                image = Image.open(file_path)
                # Calculate scaling to fit canvas while maintaining aspect ratio
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                image_ratio = image.width / image.height
                canvas_ratio = canvas_width / canvas_height
                
                if image_ratio > canvas_ratio:
                    new_width = canvas_width
                    new_height = int(canvas_width / image_ratio)
                else:
                    new_height = canvas_height
                    new_width = int(canvas_height * image_ratio)
                
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.current_image = ImageTk.PhotoImage(image)
                self.original_image = image  # Keep original image for reference
                
                # Clear canvas and display image
                self.canvas.delete("all")
                self.canvas.create_image(
                    new_width // 2,
                    new_height // 2,
                    anchor=tk.CENTER,
                    image=self.current_image,
                    tags="image"
                )
                
                # Update scroll region
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open image: {str(e)}")
                
    def save_image(self):
        """Save the current image"""
        if not self.current_image:
            messagebox.showwarning("Warning", "No image to save!")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg;*.jpeg"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                # Get canvas content as image
                self.canvas.postscript(file="temp.eps")
                img = Image.open("temp.eps")
                img.save(file_path)
                os.remove("temp.eps")
                messagebox.showinfo("Success", "Image saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")
                
    def add_color(self):
        """Add a color to the palette"""
        color = colorchooser.askcolor(title="Choose color")[1]
        if color:
            self.palette_colors.append(color)
            self.update_palette_view()
            
    def extract_colors(self):
        """Extract colors from the current image"""
        if not self.current_image:
            messagebox.showwarning("Warning", "No image loaded!")
            return
            
        try:
            # Convert PhotoImage to PIL Image
            self.canvas.postscript(file="temp.eps")
            image = Image.open("temp.eps")
            image = image.convert('RGB')
            os.remove("temp.eps")
            
            # Get dominant colors
            pixels = list(image.getdata())
            pixel_count = {}
            for pixel in pixels:
                pixel_count[pixel] = pixel_count.get(pixel, 0) + 1
            
            # Sort by frequency and take top 16 colors
            sorted_colors = sorted(pixel_count.items(), key=lambda x: x[1], reverse=True)
            self.palette_colors = [f'#{r:02x}{g:02x}{b:02x}' for (r, g, b), _ in sorted_colors[:16]]
            self.update_palette_view()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract colors: {str(e)}")
            
    def update_palette_view(self):
        """Update the palette display"""
        # Clear existing colors
        for widget in self.palette_frame.winfo_children():
            widget.destroy()
            
        # Configure grid
        cols = 4
        for i, color in enumerate(self.palette_colors):
            swatch_frame = ttk.Frame(self.palette_frame, style='Dark.TFrame')
            row = i // cols
            col = i % cols
            swatch_frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            
            # Create color swatch
            swatch = tk.Canvas(
                swatch_frame,
                width=30,
                height=30,
                bg=color,
                highlightthickness=1,
                highlightbackground="#666666"
            )
            swatch.pack(padx=2, pady=2)
            
            # Bind right-click to remove color
            swatch.bind('<Button-3>', lambda e, idx=i: self.remove_color(idx))
            # Bind left-click to copy color
            swatch.bind('<Button-1>', lambda e, c=color: self.copy_color(c))
            
    def remove_color(self, index):
        """Remove a color from the palette"""
        if 0 <= index < len(self.palette_colors):
            self.palette_colors.pop(index)
            self.update_palette_view()
            
    def copy_color(self, color):
        """Copy color hex value to clipboard"""
        self.clipboard_clear()
        self.clipboard_append(color)
        messagebox.showinfo("Color Copied", f"Color {color} copied to clipboard!")
            
    def crop_image(self):
        """Crop the current image"""
        if not self.current_image:
            messagebox.showwarning("Warning", "No image loaded!")
            return
        
        self.canvas.bind('<Button-1>', self.start_crop)
        self.canvas.bind('<B1-Motion>', self.update_crop)
        self.canvas.bind('<ButtonRelease-1>', self.end_crop)
        self.canvas.config(cursor="crosshair")
        
        messagebox.showinfo("Crop Tool", "Click and drag to select crop area")
        
    def start_crop(self, event):
        self.crop_start = (event.x, event.y)
        self.crop_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="white",
            dash=(4, 4)
        )
        
    def update_crop(self, event):
        if hasattr(self, 'crop_start'):
            self.canvas.coords(self.crop_rect,
                             self.crop_start[0], self.crop_start[1],
                             event.x, event.y)
            
    def end_crop(self, event):
        """Handle the end of a crop operation"""
        if not hasattr(self, 'crop_start'):
            return
            
        # Check if there's an image to crop
        if not hasattr(self, 'original_image'):
            messagebox.showwarning("Warning", "No image to crop!")
            return

        try:
            # Get crop coordinates
            x1, y1 = self.crop_start
            x2, y2 = event.x, event.y
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)

            # Clean up selection rectangle
            self.canvas.delete(self.crop_rect)
            self.canvas.unbind('<Button-1>')
            self.canvas.unbind('<B1-Motion>')
            self.canvas.unbind('<ButtonRelease-1>')
            self.canvas.config(cursor="")
            del self.crop_start

            # Check if selection is too small
            if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
                messagebox.showwarning("Warning", "Selection area is too small!")
                return

            # Get canvas scale to adjust crop coordinates
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            img_width = self.original_image.width
            img_height = self.original_image.height

            # Convert canvas coordinates to image coordinates
            scale_x = img_width / canvas_width
            scale_y = img_height / canvas_height
            
            img_x1 = int(x1 * scale_x)
            img_y1 = int(y1 * scale_y)
            img_x2 = int(x2 * scale_x)
            img_y2 = int(y2 * scale_y)
            
            # Ensure coordinates are within image bounds
            img_x1 = max(0, min(img_x1, img_width))
            img_y1 = max(0, min(img_y1, img_height))
            img_x2 = max(0, min(img_x2, img_width))
            img_y2 = max(0, min(img_y2, img_height))
            
            # Check if crop area is valid
            if img_x1 == img_x2 or img_y1 == img_y2:
                messagebox.showwarning("Warning", "Invalid crop area selected!")
                return

            # Crop the image
            cropped_image = self.original_image.crop((img_x1, img_y1, img_x2, img_y2))
            self.original_image = cropped_image

            # Display cropped image
            canvas_ratio = canvas_width / canvas_height
            image_ratio = cropped_image.width / cropped_image.height

            if image_ratio > canvas_ratio:
                new_width = canvas_width
                new_height = int(canvas_width / image_ratio)
            else:
                new_height = canvas_height
                new_width = int(canvas_height * image_ratio)

            resized = cropped_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.current_image = ImageTk.PhotoImage(resized)
            
            # Update canvas with cropped image
            self.canvas.delete("image")
            self.canvas.create_image(
                new_width // 2,
                new_height // 2,
                anchor=tk.CENTER,
                image=self.current_image,
                tags="image"
            )
            
            # Update scroll region
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to crop image: {str(e)}")
            # Clean up on error
            if hasattr(self, 'crop_rect'):
                self.canvas.delete(self.crop_rect)
            self.canvas.config(cursor="")
        
    def remove_background(self):
        """Remove background from the current image"""
        if not hasattr(self, 'original_image'):
            messagebox.showwarning("Warning", "No image loaded!")
            return
        
        try:
            # Show loading cursor
            self.config(cursor="wait")
            self.update()
            
            # Convert PIL image to OpenCV format
            img_array = np.array(self.original_image)
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # Remove background
            result = self.image_processor.remove_background(img_array)
            
            if result is not None:
                # Convert back to PIL Image
                result_pil = Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGRA2RGBA))
                self.original_image = result_pil
                
                # Update display
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                image_ratio = result_pil.width / result_pil.height
                canvas_ratio = canvas_width / canvas_height
                
                if image_ratio > canvas_ratio:
                    new_width = canvas_width
                    new_height = int(canvas_width / image_ratio)
                else:
                    new_height = canvas_height
                    new_width = int(canvas_height * image_ratio)
                
                resized = result_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.current_image = ImageTk.PhotoImage(resized)
                
                # Update canvas
                self.canvas.delete("image")
                self.canvas.create_image(
                    new_width // 2,
                    new_height // 2,
                    anchor=tk.CENTER,
                    image=self.current_image,
                    tags="image"
                )
                
                # Update scroll region
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                
                messagebox.showinfo("Success", "Background removed successfully!")
            else:
                messagebox.showerror("Error", "Failed to remove background")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove background: {str(e)}")
        finally:
            # Restore cursor
            self.config(cursor="")
        
    def export_sprite_sheet(self):
        """Export the current image as a sprite sheet"""
        if not self.current_image:
            messagebox.showwarning("Warning", "No image loaded!")
            return
            
        messagebox.showinfo("Info", "Sprite sheet export coming soon!")
        
    def zoom_image(self, factor):
        """Zoom the image by a factor"""
        if not self.current_image:
            return
            
        self.zoom_level *= factor
        self.zoom_level = max(0.1, min(5.0, self.zoom_level))  # Limit zoom range
        
        # Update zoom label
        self.zoom_label.configure(text=f"{int(self.zoom_level * 100)}%")
        
        # Resize image
        if hasattr(self, 'original_image'):
            width = int(self.original_image.width * self.zoom_level)
            height = int(self.original_image.height * self.zoom_level)
            resized = self.original_image.resize((width, height), Image.Resampling.LANCZOS)
            self.current_image = ImageTk.PhotoImage(resized)
            
            # Update canvas
            self.canvas.delete("image")
            self.canvas.create_image(
                width // 2, height // 2,
                image=self.current_image,
                tags="image"
            )
            
            # Update scroll region
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
    def mouse_wheel_zoom(self, event):
        """Handle mouse wheel zoom"""
        if event.delta > 0:
            self.zoom_image(1.1)
        else:
            self.zoom_image(0.9)
            
    def fit_image(self):
        """Fit image to canvas size"""
        if not hasattr(self, 'original_image'):
            return
            
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Calculate zoom level to fit
        width_ratio = canvas_width / self.original_image.width
        height_ratio = canvas_height / self.original_image.height
        self.zoom_level = min(width_ratio, height_ratio)
        
        # Apply zoom
        self.zoom_image(1)  # Use 1 as factor since we've already set zoom_level

    def on_window_resize(self, event):
        """Handle window resize events"""
        # Only handle main window resizes
        if event.widget == self:
            # Get new canvas size
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Check if size actually changed
            current_size = (canvas_width, canvas_height)
            if self.last_canvas_size == current_size:
                return
            self.last_canvas_size = current_size

            # Update image if one is loaded
            if hasattr(self, 'original_image'):
                # Calculate new size maintaining aspect ratio
                image_ratio = self.original_image.width / self.original_image.height
                canvas_ratio = canvas_width / canvas_height
                
                if image_ratio > canvas_ratio:
                    new_width = canvas_width
                    new_height = int(canvas_width / image_ratio)
                else:
                    new_height = canvas_height
                    new_width = int(canvas_height * image_ratio)
                
                # Resize image
                resized = self.original_image.resize(
                    (int(new_width * self.zoom_level), 
                     int(new_height * self.zoom_level)), 
                    Image.Resampling.LANCZOS
                )
                self.current_image = ImageTk.PhotoImage(resized)
                
                # Update canvas
                self.canvas.delete("image")
                self.canvas.create_image(
                    new_width // 2,
                    new_height // 2,
                    anchor=tk.CENTER,
                    image=self.current_image,
                    tags="image"
                )
                
                # Update scroll region
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # Update welcome message position if no image
            elif self.canvas.find_withtag("welcome"):
                self.canvas.coords("welcome", canvas_width // 2, canvas_height // 2)


def main():
    # Enable DPI awareness
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    app = SpriteCraftEditor()
    
    try:
        app.mainloop()
    except Exception as e:
        print(f"Error running application: {str(e)}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    import os
    sys.exit(main())
