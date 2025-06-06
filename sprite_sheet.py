import cv2
import numpy as np
import json
from PIL import Image

class SpriteSheetGenerator:
    def __init__(self):
        self.images = []
        self.metadata = {"frames": []}
        
    def add_image(self, image):
        """Add an image to the sprite sheet"""
        if isinstance(image, np.ndarray):
            # Convert OpenCV image to PIL
            image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        self.images.append(image)
        
    def clear_images(self):
        """Clear all images"""
        self.images = []
        self.metadata = {"frames": []}
        
    def generate_sheet(self, padding=2, method="grid"):
        """Generate sprite sheet using specified method"""
        if not self.images:
            raise ValueError("No images to generate sprite sheet")
            
        if method == "grid":
            return self._generate_grid_sheet(padding)
        elif method == "packed":
            return self._generate_packed_sheet(padding)
        else:
            raise ValueError(f"Unknown method: {method}")
            
    def _generate_grid_sheet(self, padding):
        """Generate sprite sheet in a grid layout"""
        # Find maximum dimensions
        max_width = max(img.width for img in self.images)
        max_height = max(img.height for img in self.images)
        
        # Calculate optimal grid
        n_images = len(self.images)
        cols = int(np.ceil(np.sqrt(n_images)))
        rows = int(np.ceil(n_images / cols))
        
        # Create sheet
        sheet_width = cols * (max_width + padding) - padding
        sheet_height = rows * (max_height + padding) - padding
        sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
        
        # Place images
        for i, img in enumerate(self.images):
            row = i // cols
            col = i % cols
            x = col * (max_width + padding)
            y = row * (max_height + padding)
            
            # Center image in its cell
            x_offset = (max_width - img.width) // 2
            y_offset = (max_height - img.height) // 2
            
            sheet.paste(img, (x + x_offset, y + y_offset))
            
            # Add metadata
            self.metadata["frames"].append({
                "filename": f"sprite_{i}",
                "frame": {
                    "x": x + x_offset,
                    "y": y + y_offset,
                    "w": img.width,
                    "h": img.height
                },
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {
                    "x": 0,
                    "y": 0,
                    "w": img.width,
                    "h": img.height
                },
                "sourceSize": {
                    "w": img.width,
                    "h": img.height
                }
            })
            
        return sheet
        
    def _generate_packed_sheet(self, padding):
        """Generate sprite sheet using bin packing algorithm"""
        # TODO: Implement bin packing algorithm for optimal space usage
        return self._generate_grid_sheet(padding)
        
    def save_sheet(self, image_path, metadata_path):
        """Save sprite sheet and metadata"""
        if not self.images:
            raise ValueError("No sprite sheet generated")
            
        # Generate and save sheet
        sheet = self.generate_sheet()
        sheet.save(image_path)
        
        # Save metadata
        with open(metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=4)
            
    def load_sheet(self, image_path, metadata_path):
        """Load existing sprite sheet and metadata"""
        # Load metadata
        with open(metadata_path, 'r') as f:
            self.metadata = json.load(f)
            
        # Load sheet
        sheet = Image.open(image_path)
        
        # Extract individual sprites
        self.images = []
        for frame in self.metadata["frames"]:
            f = frame["frame"]
            sprite = sheet.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))
            self.images.append(sprite)
            
        return self.images
