import sys
from PyQt6.QtWidgets import QApplication
from gui import MatrixFilterApp

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    window = MatrixFilterApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()