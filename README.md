# SpriteCraft Editor

SpriteCraft Editor is a free, open-source, cross-platform photo editing application tailored for game developers and digital artists. It provides powerful tools for creating, editing, and compiling game-ready assets, such as sprite sheets, with a focus on intuitive workflows and advanced editing features.

## Features

- Image Import and Management
  - Support for PNG, JPEG, BMP, GIF, and WebP formats
  - Drag-and-drop functionality
  - Batch processing capabilities
  - Animated GIF frame extraction

- Advanced Editing Tools
  - Pixel-perfect cropping with grid overlays
  - AI-powered background removal
  - High-quality image scaling
  - Color adjustment tools
  - Pixel art creation tools

- Sprite Sheet Creation
  - Grid-based sprite sheet generation
  - Auto-packing for optimal space usage
  - Export with metadata for game engines
  - Animation strip support

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/spritecraft-editor.git
cd spritecraft-editor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

## Development Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install development dependencies:
```bash
pip install -r requirements.txt
```

3. Run tests:
```bash
python -m pytest tests.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with PyQt5
- Uses OpenCV for image processing
- TensorFlow for AI-powered features
