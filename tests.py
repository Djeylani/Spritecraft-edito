import pytest
import os
import numpy as np
import cv2
from PIL import Image
from sprite_sheet import SpriteSheetGenerator
from palette_editor import PaletteEditor
from plugin_manager import PluginManager

@pytest.fixture
def test_image():
    """Create a test image for use in tests"""
    # Create a simple gradient image
    width, height = 100, 100
    image = np.zeros((height, width, 3), dtype=np.uint8)
    for i in range(width):
        for j in range(height):
            image[j, i] = [i * 255 // width, j * 255 // height, 128]
    return image

def test_sprite_sheet_generator():
    """Test sprite sheet generation"""
    generator = SpriteSheetGenerator()
    
    # Create test images
    img1 = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
    img2 = Image.new('RGBA', (32, 32), (0, 255, 0, 255))
    
    generator.add_image(img1)
    generator.add_image(img2)
    
    # Generate sheet
    sheet = generator.generate_sheet(padding=2)
    
    # Verify dimensions
    assert sheet.width == 66  # 2 * 32 + 2 padding
    assert sheet.height == 32
    
    # Verify metadata
    assert len(generator.metadata["frames"]) == 2
    
def test_palette_editor():
    """Test palette editor functionality"""
    editor = PaletteEditor()
    
    # Test adding colors
    editor.add_color(255, 0, 0)
    editor.add_color(0, 255, 0)
    editor.add_color(0, 0, 255)
    
    assert len(editor.palette) == 3
    
    # Test removing color
    editor.remove_color(1)
    assert len(editor.palette) == 2
    
    # Test similar color matching
    similar = editor.get_similar_color(240, 10, 10)
    assert similar == (255, 0, 0)  # Should match red
    
def test_plugin_manager():
    """Test plugin system"""
    manager = PluginManager()
    
    # Create test plugin
    os.makedirs("plugins", exist_ok=True)
    with open("plugins/test_plugin.py", "w") as f:
        f.write("""
def apply(x):
    return x * 2
""")
    
    # Load plugins
    manager.load_plugins()
    
    # Test plugin execution
    result = manager.apply_plugin("test_plugin", 5)
    assert result == 10
    
    # Clean up
    os.remove("plugins/test_plugin.py")
    
def test_dithering_plugin(test_image):
    """Test the dithering plugin"""
    plugin_manager = PluginManager()
    plugin_manager.load_plugins()
    
    # Test Floyd-Steinberg dithering
    dithered = plugin_manager.apply_plugin('dithering', test_image, pattern='floyd-steinberg')
    assert dithered is not None
    assert dithered.shape == test_image.shape
    
    # Test ordered dithering
    dithered = plugin_manager.apply_plugin('dithering', test_image, pattern='ordered')
    assert dithered is not None
    assert dithered.shape == test_image.shape
    
    # Test random dithering
    dithered = plugin_manager.apply_plugin('dithering', test_image, pattern='random')
    assert dithered is not None
    assert dithered.shape == test_image.shape
    
def test_edge_detection_plugin(test_image):
    """Test the edge detection plugin"""
    plugin_manager = PluginManager()
    plugin_manager.load_plugins()
    
    # Test Sobel edge detection
    edges = plugin_manager.apply_plugin('edge_detection', test_image, method='sobel')
    assert edges is not None
    assert edges.shape == test_image.shape
    
    # Test Canny edge detection
    edges = plugin_manager.apply_plugin('edge_detection', test_image, method='canny')
    assert edges is not None
    assert edges.shape == test_image.shape
    
    # Test pixel edge detection
    edges = plugin_manager.apply_plugin('edge_detection', test_image, method='pixel')
    assert edges is not None
    assert edges.shape == test_image.shape

def test_plugin_parameters():
    """Test plugin parameter validation"""
    plugin_manager = PluginManager()
    plugin_manager.load_plugins()
    
    # Test dithering plugin parameters
    dithering = plugin_manager.get_plugin('dithering')
    params = dithering.get_parameters()
    assert 'pattern' in params
    assert params['pattern']['type'] == 'string'
    assert 'floyd-steinberg' in params['pattern']['enum']
    
    # Test edge detection plugin parameters
    edge_detection = plugin_manager.get_plugin('edge_detection')
    params = edge_detection.get_parameters()
    assert 'method' in params
    assert params['method']['type'] == 'string'
    assert 'threshold' in params
    assert params['threshold']['type'] == 'integer'
    
if __name__ == "__main__":
    pytest.main([__file__])
