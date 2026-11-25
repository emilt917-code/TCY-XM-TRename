"""重命名执行器与撤销日志（JSONL，每条含旧/新完整路径）。"""
from __future__ import annotations

import json
import os
import shutil
import time


class RenameExecutor:
    """执行 preview 结果。dry_run=True 只演练不做任何改动。"""

    def __init__(self, journal_path: str | None = None):
        self.journal_path = journal_path

    def execute(self, items, base_dir: str | None = None) -> tuple[list, list]:
        """返回 (成功记录, 失败记录)。记录含 old/new 完整路径。"""
        done, failed = [], []
        for it in items:
            old_name = f"{it.stem}.{it.ext}" if it.ext else it.stem
            new_name = f"{it.new_stem}.{it.new_ext}" if it.new_ext else it.new_stem
            if old_name == new_name:
                continue
            old_path = os.path.join(base_dir or os.path.dirname(it.ctx.path) or ".", old_name)
            parent = os.path.dirname(old_path)
            if getattr(it, "new_subdir", ""):
                parent = os.path.join(parent, it.new_subdir)
                os.makedirs(parent, exist_ok=True)
            new_path = os.path.join(parent, new_name)
            if os.path.exists(new_path) and new_path != old_path:
                failed.append({"old": old_path, "new": new_path,
                               "error": "target exists"})
                continue
            try:
                if not os.path.exists(old_path):
                    raise FileNotFoundError(old_path)
                if not self.dry_run:
                    os.rename(old_path, new_path)
                done.append({"old": old_path, "new": new_path, "ts": time.time()})
            except OSError as e:
                failed.append({"old": old_path, "new": new_path, "error": str(e)})
        if done and self.journal_path and not self.dry_run:
            with open(self.journal_path, "a", encoding="utf-8") as f:
                for rec in done:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return done, failed

    dry_run: bool = False


class UndoManager:
    """从日志回滚：默认整批回滚最近一次操作。"""

    def __init__(self, journal_path: str):
        self.journal_path = journal_path

    def _read(self) -> list[list[dict]]:
        batches, cur_ts = [], None
        with open(self.journal_path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                ts = rec.get("ts", 0)
                if cur_ts is None or ts - cur_ts > 5:
                    batches.append([])
                    cur_ts = ts
                batches[-1].append(rec)
        return batches

    def last_batch(self) -> list[dict] | None:
        batches = self._read()
        return batches[-1] if batches else None

    def undo_last(self, dry_run: bool = False) -> tuple[list, list]:
        batch = self.last_batch() or []
        done, failed = [], []
        # 逆序回滚
        for rec in reversed(batch):
            old, new = rec["old"], rec["new"]
            try:
                if not dry_run:
                    os.rename(new, old)
                done.append(rec)
            except OSError as e:
                failed.append({**rec, "error": str(e)})
        return done, failed
