import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton

def main():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Test Window")
    window.setGeometry(100, 100, 400, 300)
    
    button = QPushButton("Hello World", window)
    button.move(150, 120)
    
    window.show()
    return app.exec()

if __name__ == "__main__":
    main()
