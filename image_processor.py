import cv2
import numpy as np

class ImageProcessor:
    """Class to handle image processing tasks"""
    def __init__(self):
        pass

    def remove_background(self, image_array, conservative=False):
        """Remove background using OpenCV
        
        Args:
            image_array: Input image as numpy array (BGR or BGRA format)
            conservative: If True, use more conservative settings to preserve foreground
            
        Returns:
            Image with transparent background (BGRA format)
        """
        try:
            # Convert to RGB if needed
            if image_array.shape[2] == 3:
                # BGR to RGB
                rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            else:
                # BGRA to RGB (discard alpha)
                rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGRA2RGB)
            
            # Special handling for white backgrounds
            # Create a mask for white pixels
            lower_white = np.array([220, 220, 220])
            upper_white = np.array([255, 255, 255])
            white_mask = cv2.inRange(rgb_image, lower_white, upper_white)
            
            # Invert to get foreground
            foreground_mask = cv2.bitwise_not(white_mask)
            
            # Apply morphological operations to clean up the mask
            kernel = np.ones((3,3), np.uint8)
            foreground_mask = cv2.morphologyEx(foreground_mask, cv2.MORPH_OPEN, kernel)
            foreground_mask = cv2.morphologyEx(foreground_mask, cv2.MORPH_CLOSE, kernel)
            
            # Find contours in the foreground mask
            contours, _ = cv2.findContours(foreground_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Create a refined mask
            refined_mask = np.zeros_like(foreground_mask)
            
            if contours:
                # Sort contours by area (descending)
                contours = sorted(contours, key=cv2.contourArea, reverse=True)
                
                # Take only significant contours
                significant_contours = []
                max_area = cv2.contourArea(contours[0])
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    # Keep contours that are at least 5% of the largest contour
                    if area > max_area * 0.05:
                        significant_contours.append(contour)
                
                # Draw all significant contours
                cv2.drawContours(refined_mask, significant_contours, -1, 255, -1)
                
                # Dilate slightly to ensure we don't cut off edges
                refined_mask = cv2.dilate(refined_mask, kernel, iterations=1)
            
            # Create alpha channel (255 for foreground, 0 for background)
            alpha_channel = refined_mask
            
            # Split the original image into channels
            if image_array.shape[2] == 3:
                b, g, r = cv2.split(image_array)
            else:
                b, g, r, _ = cv2.split(image_array)
                
            # Merge with the new alpha channel
            result = cv2.merge([b, g, r, alpha_channel])
            
            return result
            
        except Exception as e:
            print(f"Error during background removal processing: {str(e)}")
            return None

    def resize_image(self, image, width, height, method='nearest'):
        """Resize image using specified method"""
        interpolation = cv2.INTER_NEAREST if method == 'nearest' else cv2.INTER_CUBIC
        return cv2.resize(image, (width, height), interpolation=interpolation)
        
    def rotate_image(self, image, angle, center=None):
        """Rotate image by angle degrees"""
        if center is None:
            center = (image.shape[1] // 2, image.shape[0] // 2)
            
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]))
        
    def adjust_brightness_contrast(self, image, brightness=0, contrast=0):
        """Adjust image brightness and contrast"""
        if brightness != 0:
            if brightness > 0:
                shadow = brightness
                highlight = 255
            else:
                shadow = 0
                highlight = 255 + brightness
            alpha_b = (highlight - shadow) / 255
            gamma_b = shadow
            
            image = cv2.addWeighted(image, alpha_b, image, 0, gamma_b)
            
        if contrast != 0:
            f = 131 * (contrast + 127) / (127 * (131 - contrast))
            alpha_c = f
            gamma_c = 127 * (1 - f)
            
            image = cv2.addWeighted(image, alpha_c, image, 0, gamma_c)
            
        return image