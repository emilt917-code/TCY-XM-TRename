"""执行器与撤销测试。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ultrarename.engine import Pipeline, RenameExecutor, ReplaceRule, UndoManager  # noqa: E402


def _make(tmp_path, names):
    for n in names:
        (tmp_path / n).write_text("x")
    return [str(tmp_path / n) for n in names]


def test_execute_and_undo(tmp_path):
    journal = tmp_path / "journal.jsonl"
    paths = _make(tmp_path, ["a1.txt", "a2.txt"])
    p = Pipeline([ReplaceRule("a", "b")])
    items = p.preview(paths)
    ex = RenameExecutor(str(journal))
    done, failed = ex.execute(items, base_dir=str(tmp_path))
    assert len(done) == 2 and not failed
    assert sorted(os.listdir(tmp_path)) == ["b1.txt", "b2.txt", "journal.jsonl"]

    u = UndoManager(str(journal))
    done_u, failed_u = u.undo_last()
    assert not failed_u and len(done_u) == 2
    assert sorted(n for n in os.listdir(tmp_path) if n.endswith(".txt")) == ["a1.txt", "a2.txt"]


def test_execute_target_exists_fails(tmp_path):
    paths = _make(tmp_path, ["a.txt", "b.txt"])
    p = Pipeline([ReplaceRule("a", "b")])
    items = p.preview(paths)
    ex = RenameExecutor(None)
    done, failed = ex.execute(items, base_dir=str(tmp_path))
    assert not done and len(failed) == 1 and failed[0]["error"] == "target exists"


def test_dry_run_no_changes(tmp_path):
    paths = _make(tmp_path, ["a.txt"])
    ex = RenameExecutor(None)
    ex.dry_run = True
    items = Pipeline([ReplaceRule("a", "b")]).preview(paths)
    done, failed = ex.execute(items, base_dir=str(tmp_path))
    assert len(done) == 1
    assert os.path.exists(str(tmp_path / "a.txt"))
