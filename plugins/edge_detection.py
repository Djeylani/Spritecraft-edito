import cv2
import numpy as np

def apply(image, method='sobel', threshold=100):
    """Apply edge detection to an image
    
    Args:
        image: numpy.ndarray - Input image
        method: str - Edge detection method ('sobel', 'canny', or 'pixel')
        threshold: int - Edge detection threshold
        
    Returns:
        numpy.ndarray - Edge detected image
    """
    # Convert to grayscale if needed
    if len(image.shape) > 2:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
        
    if method == 'sobel':
        # Sobel edge detection
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        # Combine horizontal and vertical edges
        edges = np.sqrt(sobel_x**2 + sobel_y**2)
        edges = np.uint8(np.clip(edges, 0, 255))
        
    elif method == 'canny':
        # Canny edge detection
        edges = cv2.Canny(gray, threshold, threshold * 2)
        
    elif method == 'pixel':
        # Simple pixel difference edge detection
        edges = np.zeros_like(gray)
        height, width = gray.shape
        
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                diff_x = int(gray[y, x + 1]) - int(gray[y, x - 1])
                diff_y = int(gray[y + 1, x]) - int(gray[y - 1, x])
                edge_strength = np.sqrt(diff_x**2 + diff_y**2)
                edges[y, x] = 255 if edge_strength > threshold else 0
                
    # Convert back to color if input was color
    if len(image.shape) > 2:
        edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        
    return edges

def get_parameters():
    """Return the parameters that this plugin accepts"""
    return {
        'method': {
            'type': 'string',
            'default': 'sobel',
            'enum': ['sobel', 'canny', 'pixel'],
            'description': 'Edge detection method to use'
        },
        'threshold': {
            'type': 'integer',
            'default': 100,
            'minimum': 0,
            'maximum': 255,
            'description': 'Edge detection threshold'
        }
    }
