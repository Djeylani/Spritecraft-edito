import cv2
import numpy as np

def apply(image, pixel_size=8):
    """Apply pixelation effect to an image
    
    Args:
        image: numpy.ndarray - Input image
        pixel_size: int - Size of pixels in the pixelated image
        
    Returns:
        numpy.ndarray - Pixelated image
    """
    # Get image dimensions
    height, width = image.shape[:2]
    
    # Calculate new dimensions
    new_height = height // pixel_size
    new_width = width // pixel_size
    
    # Resize down
    temp = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    
    # Resize back up
    return cv2.resize(temp, (width, height), interpolation=cv2.INTER_NEAREST)
