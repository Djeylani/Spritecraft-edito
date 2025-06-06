import cv2
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

class ImageProcessor:
    """Class to handle image processing tasks"""
    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the pre-trained DeepLabV3 model"""
        try:
            # Load pre-trained DeepLabV3 model from TensorFlow Hub
            # Using the quantized version for potentially better performance on CPU
            model_url = 'https://tfhub.dev/tensorflow/lite-model/deeplabv3/1/default/1'
            self.model = hub.load(model_url)
            print("DeepLabV3 model loaded successfully.")
        except Exception as e:
            print(f"Error loading DeepLabV3 model: {str(e)}")
            self.model = None

    def remove_background(self, image_array):
        """Remove background using DeepLabV3"""
        if self.model is None:
            print("DeepLabV3 model not loaded. Cannot perform background removal.")
            return None

        try:
            # Convert BGR to RGB (DeepLabV3 expects RGB)
            rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)

            # Preprocess image for the model
            input_size = (513, 513) # DeepLabV3 input size
            input_tensor = tf.convert_to_tensor(rgb_image, dtype=tf.float32)
            input_tensor = tf.expand_dims(input_tensor, 0) # Add batch dimension
            input_tensor = tf.image.resize(input_tensor, input_size) # Resize
            input_tensor = input_tensor / 255.0  # Normalize to [0, 1]

            # Get prediction (segmentation mask)
            # The model returns a dictionary, the mask is under the key 'segmentation_masks'
            predictions = self.model(input_tensor)
            segmentation_mask = predictions['segmentation_masks']

            # Post-process the mask
            # The mask is typically a float32 tensor with values between 0 and 1
            # We need to threshold it to get a binary mask (background vs foreground)
            # A common threshold is 0.5, but this might need tuning
            binary_mask = (segmentation_mask > 0.5)
            binary_mask = tf.squeeze(binary_mask, axis=0) # Remove batch dimension
            binary_mask = tf.image.resize(tf.cast(binary_mask, tf.float32), (image_array.shape[0], image_array.shape[1])) # Resize to original image size
            binary_mask = tf.cast(binary_mask, tf.uint8).numpy() # Convert to uint8 numpy array

            # Create a 4-channel image (RGBA) with transparent background
            # The mask is 1 channel (height, width, 1)
            mask_3_channel = cv2.cvtColor(binary_mask, cv2.COLOR_GRAY2BGR) # Convert mask to 3 channels

            # Create the alpha channel from the binary mask
            alpha_channel = np.squeeze(binary_mask) * 255 # Scale mask to 0-255 for alpha
            alpha_channel = np.expand_dims(alpha_channel, axis=-1) # Add channel dimension

            # Combine original image (BGR) with the alpha channel
            # Need to ensure original image is BGR for cv2.merge
            if image_array.shape[-1] == 3:
                 b, g, r = cv2.split(image_array)
            elif image_array.shape[-1] == 4:
                 b, g, r, _ = cv2.split(image_array) # Discard existing alpha if any
            else:
                 # Handle other potential channel counts if necessary
                 return None # Or raise an error

            result = cv2.merge([b, g, r, alpha_channel]) # Merge B, G, R, and Alpha

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
