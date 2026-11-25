"""规则面板：卡片列表 + 添加规则 + 预设保存/加载。"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from .rule_card import RuleCard
from .rule_specs import ORDER, SPEC


class RulesPanel(QWidget):
    """规则卡片区。build_rules() 返回引擎可用的规则对象列表。"""

    PRESET_DIR = os.path.expanduser("~/.ultrarename/presets")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: list[RuleCard] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 顶部按钮行
        top = QHBoxLayout()
        self.btn_add = QPushButton("＋ 添加规则")
        self.btn_add.clicked.connect(self._add_menu)
        top.addWidget(self.btn_add)
        top.addStretch(1)
        top.addWidget(QLabel("预设:"))
        self.cmb_preset = QComboBox()
        self._reload_presets()
        top.addWidget(self.cmb_preset, 1)
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save_preset)
        btn_load = QPushButton("载入")
        btn_load.clicked.connect(self._load_preset)
        btn_del = QPushButton("删除预设")
        btn_del.clicked.connect(self._del_preset)
        for b in (btn_save, btn_load, btn_del):
            top.addWidget(b)
        root.addLayout(top)

        # 卡片滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.lay = QVBoxLayout(self.container)
        self.lay.setAlignment(Qt.AlignTop)
        self.lay.setSpacing(6)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

    # ------------------------------------------------ 卡片管理
    def add_rule(self, type_name: str, params: dict | None = None,
                 enabled: bool = True) -> RuleCard:
        card = RuleCard(type_name, params, enabled)
        card.changed.connect(self.refresh_requested)
        card.request_move.connect(self._move)
        card.request_remove.connect(self._remove)
        self.cards.append(card)
        self.lay.addWidget(card)
        self.refresh_requested.emit()
        return card

    def _add_menu(self):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        for t in ORDER:
            menu.addAction(SPEC[t]["label"], lambda t=t: self.add_rule(t))
        menu.exec(self.btn_add.mapToGlobal(self.btn_add.rect().bottomLeft()))

    def _move(self, card: RuleCard, delta: int):
        i = self.cards.index(card)
        j = i + delta
        if not (0 <= j < len(self.cards)):
            return
        self.cards[i], self.cards[j] = self.cards[j], self.cards[i]
        self.lay.takeAt(i)
        self.lay.insertWidget(j, card)
        self.refresh_requested.emit()

    def _remove(self, card: RuleCard):
        self.cards.remove(card)
        self.lay.removeWidget(card)
        card.deleteLater()
        self.refresh_requested.emit()

    # ------------------------------------------------ 引擎桥接
    def build_rules(self):
        rules = []
        for card in self.cards:
            if not card.isChecked():
                continue
            params = card.values()
            try:
                rules.append(SPEC[card.type_name]["factory"](params))
            except Exception:
                continue  # 参数不完整/脚本错误时跳过该规则，预览仍可刷新
        return rules

    def serialize(self) -> list[dict]:
        return [c.serialize() for c in self.cards]

    def load_state(self, states: list[dict]):
        for c in list(self.cards):
            self._remove(c)
        for st in states:
            self.add_rule(st["type"], st.get("params"), st.get("enabled", True))

    # ------------------------------------------------ 预设
    def _reload_presets(self):
        self.cmb_preset.clear()
        os.makedirs(self.PRESET_DIR, exist_ok=True)
        for f in sorted(os.listdir(self.PRESET_DIR)):
            if f.endswith(".json"):
                self.cmb_preset.addItem(f[:-5])

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：")
        if not (ok and name.strip()):
            return
        os.makedirs(self.PRESET_DIR, exist_ok=True)
        path = os.path.join(self.PRESET_DIR, f"{name.strip()}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.serialize(), f, ensure_ascii=False, indent=1)
        self._reload_presets()
        self.cmb_preset.setCurrentText(name.strip())

    def _load_preset(self):
        name = self.cmb_preset.currentText()
        path = os.path.join(self.PRESET_DIR, f"{name}.json")
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            self.load_state(json.load(f))

    def _del_preset(self):
        name = self.cmb_preset.currentText()
        path = os.path.join(self.PRESET_DIR, f"{name}.json")
        if name and os.path.exists(path):
            os.remove(path)
            self._reload_presets()

    from PySide6.QtCore import Signal as _Sig
    refresh_requested = _Sig()
