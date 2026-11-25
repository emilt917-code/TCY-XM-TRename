"""规则卡片：单条规则的可视化编辑器。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QToolButton, QTextEdit, QVBoxLayout,
)

from .rule_specs import SPEC


class RuleCard(QGroupBox):
    """一条规则的编辑卡片。type_name 对应 SPEC 键。"""

    def __init__(self, type_name: str, params: dict | None = None,
                 enabled: bool = True, parent=None):
        super().__init__(parent)
        self.type_name = type_name
        self.spec = SPEC[type_name]
        self.setTitle(self.spec["label"])
        self.setCheckable(True)
        self.setChecked(enabled)
        self.toggled.connect(self.changed.emit)

        lay = QVBoxLayout(self)
        grid = QGridLayout()
        self.widgets: dict[str, object] = {}
        for row, (name, label, kind, default, *rest) in enumerate(self.spec["fields"]):
            val = (params or {}).get(name, default)
            grid.addWidget(QLabel(label), row, 0)
            if kind == "text":
                w = QLineEdit(str(val))
                w.textChanged.connect(self.changed)
            elif kind == "int":
                w = QSpinBox()
                w.setRange(-99999, 999999)
                w.setValue(int(val) or 0)
                w.valueChanged.connect(self.changed)
            elif kind == "check":
                w = QCheckBox()
                w.setChecked(bool(val))
                w.toggled.connect(self.changed)
            elif kind == "combo":
                w = QComboBox()
                w.addItems(rest[0] if rest else [])
                if val in [w.itemText(i) for i in range(w.count())]:
                    w.setCurrentText(val)
                w.activated.connect(self.changed)
            elif kind == "code":
                w = QTextEdit(str(val))
                w.setFixedHeight(90)
                w.textChanged.connect(self.changed)
            else:
                raise ValueError(kind)
            self.widgets[name] = w
            grid.addWidget(w, row, 1)
        lay.addLayout(grid)

        btns = QHBoxLayout()
        btns.addStretch(1)
        for txt, cb in (("↑", self._up), ("↓", self._down), ("✕ 删除", self._del)):
            b = QToolButton() if txt in ("↑", "↓") else QPushButton(txt)
            b.setText(txt)
            b.clicked.connect(cb)
            btns.addWidget(b)
        lay.addLayout(btns)

    # ---- 对外接口
    def values(self) -> dict:
        out = {}
        for name, _l, kind, _d, *_r in self.spec["fields"]:
            w = self.widgets[name]
            if kind == "text":
                out[name] = w.text()
            elif kind == "int":
                out[name] = w.value()
            elif kind == "check":
                out[name] = w.isChecked()
            elif kind == "combo":
                out[name] = w.currentText()
            elif kind == "code":
                out[name] = w.toPlainText()
        return out

    def serialize(self) -> dict:
        return {"type": self.type_name, "enabled": self.isChecked(),
                "params": self.values()}

    def _up(self):
        self.request_move.emit(self, -1)

    def _down(self):
        self.request_move.emit(self, +1)

    def _del(self):
        self.request_remove.emit(self)

    from PySide6.QtCore import Signal as _Sig
    request_move = _Sig(object, int)
    request_remove = _Sig(object)
    changed = _Sig()