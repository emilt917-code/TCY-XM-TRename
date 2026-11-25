"""规则管道：按顺序应用规则、生成预览、检测冲突。"""
from __future__ import annotations

import os
import datetime as _dt
from dataclasses import dataclass

from .rules import FileContext, RenameItem


@dataclass
class SourceFile:
    path: str

    @property
    def stem(self) -> str:
        base = os.path.basename(self.path)
        return base.rsplit(".", 1)[0] if "." in base else base

    @property
    def ext(self) -> str:
        base = os.path.basename(self.path)
        return base.rsplit(".", 1)[1] if "." in base else ""

    def context(self, index: int) -> FileContext:
        try:
            st = os.stat(self.path)
            return FileContext(
                index=index, path=self.path, size=st.st_size,
                mtime=_dt.datetime.fromtimestamp(st.st_mtime),
                atime=_dt.datetime.fromtimestamp(st.st_atime),
                ctime=_dt.datetime.fromtimestamp(st.st_ctime),
            )
        except OSError:
            return FileContext(index=index, path=self.path)


class Pipeline:
    def __init__(self, rules):
        self.rules = list(rules)

    def preview(self, files: list[str]) -> list[RenameItem]:
        items = []
        for i, p in enumerate(files):
            sf = SourceFile(p)
            item = RenameItem(sf.stem, sf.ext, sf.context(i))
            for r in self.rules:
                r.run(item)
            if not item.new_stem:
                item.new_stem = item.stem
            if not item.new_ext:
                item.new_ext = item.ext
            items.append(item)
        return items

    @staticmethod
    def new_name(item: RenameItem) -> str:
        return f"{item.new_stem}.{item.new_ext}" if item.new_ext else item.new_stem

    @staticmethod
    def old_name(item: RenameItem) -> str:
        return f"{item.stem}.{item.ext}" if item.ext else item.stem

    def conflicts(self, items: list[RenameItem]) -> dict[str, list[str]]:
        """返回 new_name -> 涉及的旧文件名列表（>1 即冲突）。"""
        buckets: dict[str, list[str]] = {}
        for it in items:
            buckets.setdefault(self.new_name(it), []).append(self.old_name(it))
        return {k: v for k, v in buckets.items() if len(v) > 1}

    def overwrites(self, items: list[RenameItem]) -> set[str]:
        """新名撞上批内未参与重命名的旧名（危险覆盖）。"""
        old_names = {self.old_name(it) for it in items}
        new_names = {self.new_name(it) for it in items}
        untouched = old_names - new_names
        return {n for n in new_names if n in untouched}
