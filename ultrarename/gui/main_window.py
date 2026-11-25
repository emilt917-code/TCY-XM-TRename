"""UltraRename 主窗口（A-R2 骨架）：目录树 + 文件列表 + 预览 + Rename/Undo。

R3 将在此骨架上扩展规则面板区；R2 先内置少量规则保证预览可用。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QPushButton, QSplitter,
    QStatusBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QGroupBox,
    QGridLayout,
)

from ultrarename.engine import (
    Pipeline, RenameExecutor, UndoManager,
)

COLOR_CHANGED = QColor("#2e7d32")   # 将变更
COLOR_CONFLICT = QColor("#c62828")  # 冲突/覆盖


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TRename — 全能批量重命名")
        self.resize(1280, 800)
        self.pipeline = Pipeline([])
        self.executor = RenameExecutor(
            os.path.join(os.path.expanduser("~"), ".ultrarename_journal.jsonl"))
        self._current_dir = os.path.expanduser("~")
        self._dark = False
        self._build_ui()
        self._apply_light()

    # ------------------------------------------------ UI 构建
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        # 工具行
        bar = QHBoxLayout()
        btn_dir = QPushButton("选择目录…")
        btn_dir.clicked.connect(self._choose_dir)
        self.chk_recursive = QCheckBox("包含子目录")
        self.inp_filter = QLineEdit()
        self.inp_filter.setPlaceholderText("过滤：通配符如 *.mp4 或正则（留空=全部）")
        self.chk_regex_filter = QCheckBox("正则")
        self.btn_preview = QPushButton("预览")
        self.btn_preview.clicked.connect(self.refresh)
        self.btn_rename = QPushButton("执行重命名")
        self.btn_rename.clicked.connect(self._do_rename)
        self.btn_undo = QPushButton("撤销上次")
        self.btn_undo.clicked.connect(self._do_undo)
        self.btn_csv_export = QPushButton("导出CSV")
        self.btn_csv_export.clicked.connect(self._export_csv)
        self.btn_csv_import = QPushButton("导入CSV")
        self.btn_csv_import.clicked.connect(self._import_csv)
        self.btn_dark = QPushButton("🌙")
        self.btn_dark.setFixedWidth(40)
        self.btn_dark.clicked.connect(self._toggle_dark)
        for w in (btn_dir, self.chk_recursive, self.inp_filter,
                  self.chk_regex_filter, self.btn_preview, self.btn_rename,
                  self.btn_undo, self.btn_csv_export, self.btn_csv_import,
                  self.btn_dark):
            bar.addWidget(w)
        self.inp_filter.returnPressed.connect(self.refresh)
        root.addLayout(bar)

        # 主体：左目录树 / 右文件列表
        split = QSplitter(Qt.Horizontal)
        from PySide6.QtWidgets import QFileSystemModel, QTreeView
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(self._current_dir)
        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        for c in range(1, self.fs_model.columnCount()):
            self.tree.hideColumn(c)
        self.tree.doubleClicked.connect(self._on_dir_clicked)
        self.files = QTreeWidget()
        self.files.setColumnCount(3)
        self.files.setHeaderLabels(["当前文件名", "新文件名", "状态"])
        self.files.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.files.setSelectionMode(QTreeWidget.ExtendedSelection)
        split.addWidget(self.tree)
        split.addWidget(self.files)
        split.setSizes([360, 920])
        root.addWidget(split, 1)

        # 规则面板区（全量规则卡片 + 预设系统）
        from .rules_panel import RulesPanel
        self.rules_panel = RulesPanel()
        self.rules_panel.refresh_requested.connect(self.refresh)
        root.addWidget(self.rules_panel, 1)

        self.setCentralWidget(central)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("双击左侧目录加载文件，或点「选择目录…」")

    # ------------------------------------------------ 行为
    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择目录", self._current_dir)
        if d:
            self._current_dir = d
            root_idx = self.fs_model.setRootPath(d)
            self.tree.setRootIndex(root_idx)
            self.refresh()

    def _on_dir_clicked(self, idx):
        path = self.fs_model.filePath(idx)
        if os.path.isdir(path):
            self._current_dir = path
            self.refresh()

    def _collect_files(self) -> list[str]:
        base = self._current_dir
        pattern = self.inp_filter.text().strip()
        import re as _re
        import fnmatch

        def keep(name: str) -> bool:
            if not pattern:
                return True
            if self.chk_regex_filter.isChecked():
                return bool(_re.search(pattern, name))
            return fnmatch.fnmatch(name.lower(), pattern.lower())

        files: list[str] = []
        if self.chk_recursive.isChecked():
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                files += [os.path.join(dirpath, f) for f in filenames if keep(f)]
        else:
            try:
                files = [os.path.join(base, f) for f in os.listdir(base)
                         if os.path.isfile(os.path.join(base, f)) and keep(f)]
            except OSError:
                files = []
        return sorted(files)

    def _build_rules(self):
        return self.rules_panel.build_rules()

    def refresh(self):
        self.files.clear()
        rules = self._build_rules()
        self.pipeline = Pipeline(rules)
        paths = self._collect_files()
        items = self.pipeline.preview(paths)
        conflicts = self.pipeline.conflicts(items)
        overwrites = self.pipeline.overwrites(items)
        changed = 0
        for it in items:
            old, new = self.pipeline.old_name(it), self.pipeline.new_name(it)
            row = QTreeWidgetItem([old, new, ""])
            state = "不变"
            if new != old:
                state = "改名"
                row.setForeground(1, COLOR_CHANGED)
                changed += 1
            if new in conflicts:
                state = "⚠ 重名冲突"
                row.setBackground(2, COLOR_CONFLICT)
            elif new in overwrites:
                state = "⚠ 覆盖已有"
                row.setBackground(2, COLOR_CONFLICT)
            row.setText(2, state)
            self.files.addTopLevelItem(row)
        n_conf = len(conflicts) + len(overwrites)
        self.status.showMessage(
            f"{len(paths)} 个文件 | 将改名 {changed} | 冲突 {n_conf} | "
            f"目录 {self._current_dir}")

    def _do_rename(self):
        paths = [os.path.join(self._current_dir, self.files.item(i).text(0))
                 for i in range(self.files.topLevelItemCount())]
        items = self.pipeline.preview(paths)
        if self.pipeline.conflicts(items) or self.pipeline.overwrites(items):
            self.status.showMessage("存在冲突/覆盖风险，已阻止执行。请先调整规则。")
            return
        done, failed = self.executor.execute(items, base_dir=self._current_dir)
        self.status.showMessage(f"重命名完成 {len(done)}，失败 {len(failed)}")
        self.refresh()

    def _export_csv(self):
        paths = self._collect_files()
        items = Pipeline(self._build_rules()).preview(paths)
        out, _ = QFileDialog.getSaveFileName(self, "导出映射", "rename_map.csv",
                                             "CSV (*.csv)")
        if not out:
            return
        import csv as _csv
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            for it in items:
                w.writerow([self.pipeline.old_name(it), self.pipeline.new_name(it)])
        self.status.showMessage(f"已导出 {len(items)} 行映射 → {out}")

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入CSV", "",
                                              "CSV (*.csv)")
        if not path:
            return
        self.rules_panel.add_rule("ListRule", {"csv_path": path})
        self.status.showMessage(f"已加入 CSV 映射规则：{path}")

    def _do_undo(self):
        done, failed = UndoManager(self.executor.journal_path).undo_last()
        self.status.showMessage(f"撤销 {len(done)} 条，失败 {len(failed)}")
        self.refresh()

    # ------------------------------------------------ 明暗主题
    def _toggle_dark(self):
        if self._dark:
            self._apply_light()
        else:
            self._apply_dark()
        self._dark = not self._dark

    def _palette(self, base, text, btn, hl, window_txt=None):
        p = QPalette()
        p.setColor(QPalette.Window, base)
        p.setColor(QPalette.WindowText, window_txt or text)
        p.setColor(QPalette.Base, base.darker(150) if self._dark else base)
        p.setColor(QPalette.AlternateBase, base)
        p.setColor(QPalette.Text, text)
        p.setColor(QPalette.Button, btn)
        p.setColor(QPalette.ButtonText, text)
        p.setColor(QPalette.Highlight, hl)
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        return p

    def _apply_light(self):
        app = QApplication.instance()
        app.setStyle("Fusion")
        app.setPalette(self._palette(QColor("#f3f3f3"), QColor("#1a1a1a"),
                                     QColor("#e8e8e8"), QColor("#1976d2")))
        self.btn_dark.setText("🌙")

    def _apply_dark(self):
        app = QApplication.instance()
        app.setStyle("Fusion")
        p = QPalette()
        base = QColor("#2b2b2b")
        p.setColor(QPalette.Window, base)
        p.setColor(QPalette.WindowText, QColor("#dddddd"))
        p.setColor(QPalette.Base, QColor("#1e1e1e"))
        p.setColor(QPalette.AlternateBase, QColor("#353535"))
        p.setColor(QPalette.Text, QColor("#dddddd"))
        p.setColor(QPalette.Button, QColor("#3a3a3a"))
        p.setColor(QPalette.ButtonText, QColor("#dddddd"))
        p.setColor(QPalette.Highlight, QColor("#1976d2"))
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        app.setPalette(p)
        self.btn_dark.setText("☀️")


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
