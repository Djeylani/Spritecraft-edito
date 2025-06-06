from typing import List, Tuple, Optional
import numpy as np
from PIL import Image
import colorsys
import json

class PaletteEditor:
    def __init__(self):
        self.palette: List[Tuple[int, int, int]] = []
        self.max_colors = 256
        
    def add_color(self, r: int, g: int, b: int) -> bool:
        """Add a color to the palette"""
        if len(self.palette) >= self.max_colors:
            return False
            
        color = (r, g, b)
        if color not in self.palette:
            self.palette.append(color)
        return True
        
    def remove_color(self, index: int) -> bool:
        """Remove a color from the palette by index"""
        if 0 <= index < len(self.palette):
            self.palette.pop(index)
            return True
        return False
        
    def get_similar_color(self, r: int, g: int, b: int, threshold: float = 30.0) -> Optional[Tuple[int, int, int]]:
        """Find the most similar color in the palette"""
        if not self.palette:
            return None
            
        target = np.array([r, g, b])
        min_dist = float('inf')
        best_color = None
        
        for color in self.palette:
            dist = np.sqrt(np.sum((target - np.array(color)) ** 2))
            if dist < min_dist and dist <= threshold:
                min_dist = dist
                best_color = color
                
        return best_color
        
    def extract_palette(self, image: Image.Image, max_colors: int = 16) -> List[Tuple[int, int, int]]:
        """Extract a color palette from an image"""
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        quantized = image.quantize(colors=min(max_colors, self.max_colors), method=2)
        palette = quantized.getpalette()
        
        self.palette = []
        for i in range(0, min(max_colors, self.max_colors) * 3, 3):
            self.palette.append((palette[i], palette[i+1], palette[i+2]))
            
        return self.palette
        
    def save_palette(self, filename: str) -> None:
        """Save palette to GIMP palette format (.gpl)"""
        with open(filename, 'w') as f:
            f.write("GIMP Palette\n")
            f.write("Name: Custom Palette\n")
            f.write("#\n")
            
            for r, g, b in self.palette:
                name = f"RGB {r} {g} {b}"
                f.write(f"{r:3d} {g:3d} {b:3d} {name}\n")
                
    def load_palette(self, filename: str) -> None:
        """Load palette from GIMP palette format (.gpl)"""
        self.palette = []
        with open(filename, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
                
            if 'GIMP Palette' in line or 'Name:' in line:
                continue
                
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    r = int(parts[0])
                    g = int(parts[1])
                    b = int(parts[2])
                    self.add_color(r, g, b)
                except (ValueError, IndexError):
                    continue
                    
    def apply_palette(self, image: Image.Image) -> Image.Image:
        """Apply the current palette to an image"""
        if not self.palette:
            return image
            
        palette_img = Image.new('P', (1, 1))
        flat_palette = []
        for r, g, b in self.palette:
            flat_palette.extend([r, g, b])
            
        while len(flat_palette) < 768:
            flat_palette.extend([0, 0, 0])
            
        palette_img.putpalette(flat_palette)
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        return image.quantize(palette=palette_img, dither=Image.FLOYDSTEINBERG)
        
    def sort_palette(self, method: str = 'hue') -> None:
        """Sort the palette using different methods"""
        if not self.palette:
            return
            
        def get_key(color):
            h, s, v = colorsys.rgb_to_hsv(color[0]/255, color[1]/255, color[2]/255)
            if method == 'hue':
                return h
            elif method == 'saturation':
                return s
            elif method == 'brightness':
                return v
            return h
            
        self.palette.sort(key=get_key)
        
    def get_complementary_color(self, r: int, g: int, b: int) -> Tuple[int, int, int]:
        """Get the complementary color for an RGB color"""
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        h = (h + 0.5) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return (int(r*255), int(g*255), int(b*255))
        
    def create_color_ramp(self, start_color: Tuple[int, int, int], 
                         end_color: Tuple[int, int, int], 
                         steps: int) -> None:
        """Create a color ramp between two colors"""
        r1, g1, b1 = start_color
        r2, g2, b2 = end_color
        
        for i in range(steps):
            t = i / (steps - 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            self.add_color(r, g, b)
