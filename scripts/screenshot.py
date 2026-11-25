"""离屏截图验证 GUI（不依赖显示器）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ultrarename.gui.main_window import MainWindow


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ultrarename.png"
    demo_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~")
    app = QApplication([])
    w = MainWindow()
    w._current_dir = demo_dir
    # 演示：番号改名规则
    w.rules_panel.add_rule("RegexRule", {
        "match": r"^([A-Z]{2,6}-?\d{2,5}).*$", "replace": r"\1",
        "include_ext": False})
    w.resize(1280, 860)
    w.show()

    def shoot():
        w.refresh()
        w.grab().save(out)
        app.quit()

    QTimer.singleShot(800, shoot)
    app.exec()
    print("saved:", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
