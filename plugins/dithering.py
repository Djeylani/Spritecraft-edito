import cv2
import numpy as np
from PIL import Image

def apply(image, pattern='floyd-steinberg'):
    """Apply dithering effect to an image
    
    Args:
        image: numpy.ndarray - Input image (OpenCV format)
        pattern: str - Dithering pattern ('floyd-steinberg', 'ordered', or 'random')
        
    Returns:
        numpy.ndarray - Dithered image
    """
    # Convert OpenCV image to PIL Image
    if isinstance(image, np.ndarray):
        image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    
    if pattern == 'floyd-steinberg':
        # Use PIL's built-in Floyd-Steinberg dithering
        image = image.convert('RGB').convert('P', dither=Image.FLOYDSTEINBERG)
        image = image.convert('RGB')
    elif pattern == 'ordered':
        # Implement ordered dithering (Bayer matrix)
        bayer = np.array([[0, 8, 2, 10],
                         [12, 4, 14, 6],
                         [3, 11, 1, 9],
                         [15, 7, 13, 5]], dtype=np.float32)
        bayer = bayer / 16.0
        
        # Convert to numpy array
        img_array = np.array(image)
        height, width = img_array.shape[:2]
        
        # Tile the Bayer matrix
        bayer_tiled = np.tile(bayer, (height//4 + 1, width//4 + 1))[:height, :width]
        
        # Apply dithering
        img_array = (img_array / 255.0 > bayer_tiled[..., np.newaxis]) * 255
        image = Image.fromarray(img_array.astype(np.uint8))
    elif pattern == 'random':
        # Random dithering
        img_array = np.array(image)
        noise = np.random.normal(0, 30, img_array.shape)
        img_array = np.clip(img_array + noise, 0, 255)
        image = Image.fromarray(img_array.astype(np.uint8))
    
    # Convert back to OpenCV format
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

def get_parameters():
    """Return the parameters that this plugin accepts"""
    return {
        'pattern': {
            'type': 'string',
            'default': 'floyd-steinberg',
            'enum': ['floyd-steinberg', 'ordered', 'random'],
            'description': 'Dithering pattern to apply'
        }
    }
