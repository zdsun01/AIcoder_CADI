import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from app_window import AICoderApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 12)
    app.setFont(font)
    window = AICoderApp()
    window.show()
    sys.exit(app.exec_())