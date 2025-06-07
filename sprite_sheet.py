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
        """Generate sprite sheet using a basic sequential packing algorithm"""
        if not self.images:
            raise ValueError("No images to generate sprite sheet")

        # Sort images by height (descending) for slightly better packing
        # Store images with their original index to preserve metadata order
        images_with_index = sorted(enumerate(self.images), key=lambda x: x[1].height, reverse=True)

        sheet_width = 0
        sheet_height = 0
        current_x = padding
        current_y = padding
        row_max_height = 0

        # Reset metadata for packed layout
        self.metadata["frames"] = [None] * len(self.images) # Pre-allocate list

        # Create a list to hold the images in the sorted order for processing
        sorted_images = [img for _, img in images_with_index]

        # Iterate through sorted images and place them
        for original_index, img in images_with_index:
            img_width, img_height = img.size

            # Check if image fits in the current row
            if current_x + img_width + padding > sheet_width and sheet_width > 0:
                 # If not, move to the next row
                 current_x = padding
                 current_y += row_max_height + padding
                 row_max_height = 0 # Reset max height for the new row

            # Place the image
            x = current_x
            y = current_y

            # Update sheet dimensions if necessary
            sheet_width = max(sheet_width, current_x + img_width + padding)
            sheet_height = max(sheet_height, current_y + img_height + padding)

            # Update current position for the next image in the row
            current_x += img_width + padding
            row_max_height = max(row_max_height, img_height)

            # Store metadata at the original index
            self.metadata["frames"][original_index] = {
                 "filename": f"sprite_{original_index}", # Using original index for filename consistency
                 "frame": {
                     "x": x,
                     "y": y,
                     "w": img_width,
                     "h": img_height
                 },
                 "rotated": False, # Basic packing doesn't include rotation
                 "trimmed": False, # Basic packing doesn't include trimming
                 "spriteSourceSize": { # Assuming no trimming or scaling for now
                     "x": 0,
                     "y": 0,
                     "w": img_width,
                     "h": img_height
                 },
                 "sourceSize": { # Assuming no scaling for now
                     "w": img_width,
                     "h": img_height
                 }
             }

        # Final sheet dimensions (remove trailing padding from max width/height calculation)
        final_sheet_width = max(0, sheet_width - padding)
        final_sheet_height = max(0, sheet_height - padding)

        # Create the final sheet image
        sheet = Image.new("RGBA", (final_sheet_width, final_sheet_height), (0, 0, 0, 0))

        # Paste images onto the final sheet based on their calculated positions
        for i, img in enumerate(self.images):
             frame_info = self.metadata["frames"][i]["frame"]
             sheet.paste(img, (frame_info["x"], frame_info["y"]), img if img.mode == 'RGBA' else None)

        return sheet
        
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
