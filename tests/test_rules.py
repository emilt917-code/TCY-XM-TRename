"""A-R1 规则引擎全量单元测试。"""
import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ultrarename.engine import (  # noqa: E402
    CaseRule, CropRule, DateRule, ExtRule, FileContext, InsertRule,
    MoveSwapRule, NumberRule, Pipeline, RegexRule, RemoveCharset,
    RemoveFirstN, RemoveLastN, RemoveRange, ReplaceRule, ScriptRule,
)

CTX = FileContext(index=0, mtime=dt.datetime(2026, 11, 25, 12, 30),
                  today=dt.datetime(2026, 11, 25))


def t(rule, stem, ext="mp4"):
    item_stem, item_ext = rule.transform(stem, ext, CTX)
    return f"{item_stem}.{item_ext}" if item_ext else item_stem


# --- 正则
def test_regex_capture():
    assert t(RegexRule(r"^ADN-0*(\d+)$", r"ADN-\1"), "ADN-0476") == "ADN-476.mp4"

def test_regex_include_ext():
    assert t(RegexRule(r"\.jpe?g$", ".jpg", include_ext=True), "photo", "jpeg") == "photo.jpg"

def test_regex_no_match_keeps():
    assert t(RegexRule(r"^xyz", "abc"), "hello") == "hello.mp4"

# --- 大小写
def test_case_upper_lower():
    assert t(CaseRule("upper"), "abc def") == "ABC DEF.mp4"
    assert t(CaseRule("lower"), "ABC DEF") == "abc def.mp4"

def test_case_title_exceptions():
    r = CaseRule("title", exceptions=["of", "the"])
    assert t(r, "war of the worlds") == "War of the Worlds.mp4"

def test_case_sentence():
    assert t(CaseRule("sentence"), "HELLO WORLD") == "Hello world.mp4"

# --- 替换
def test_replace_all():
    assert t(ReplaceRule("a", "X"), "banana") == "bXnXnX.mp4"

def test_replace_case_insensitive_whole_word():
    r = ReplaceRule("Cat", "Dog", case_sensitive=False, whole_word=True)
    assert t(r, "cat catalog") == "Dog catalog.mp4"

def test_replace_first_only():
    assert t(ReplaceRule("a", "X", first_only=True), "banana") == "bXnana.mp4"

# --- 移除
def test_remove_first_last():
    assert t(RemoveFirstN(3), "abcdef") == "def.mp4"
    assert t(RemoveLastN(3), "abcdef") == "abc.mp4"

def test_remove_range():
    assert t(RemoveRange(2, 4), "abcdef") == "aef.mp4"

def test_remove_charset_digits_symbols():
    assert t(RemoveCharset("aeiou"), "banana") == "bnn.mp4"
    assert t(RemoveCharset("", digits=True), "ab12cd3") == "abcd.mp4"
    assert t(RemoveCharset("", symbols=True), "a-b!c d") == "abc d.mp4"
    assert t(RemoveCharset(double_spaces=True), "a  b  c") == "a b c.mp4"

def test_remove_affix():
    from ultrarename.engine import RemoveAffix
    assert t(RemoveAffix("_batch", "suffix"), "ADN-476 ごめんね。_batch") == "ADN-476 ごめんね。.mp4"
    assert t(RemoveAffix("副本", "prefix"), "副本report") == "report.mp4"
    assert t(RemoveAffix("_x", "suffix"), "name_y") == "name_y.mp4"

# --- 括号/规范化/净化/修剪/截断
def test_strip_brackets():
    from ultrarename.engine import StripBrackets
    assert t(StripBrackets(), "ADN-476 [1080p] (破解版) 名前") == "ADN-476 名前.mp4"
    assert t(StripBrackets(kinds=["()"]), "a [x] b (y)") == "a [x] b.mp4"
    assert t(StripBrackets(keep_marks=True), "a (b) c") == "a () c.mp4"

def test_normalize_fullwidth():
    from ultrarename.engine import NormalizeRule
    assert t(NormalizeRule(), "ＡＤＮ－４７６：試作品") == "ADN-476:試作品.mp4"

def test_sanitize():
    from ultrarename.engine import SanitizeRule
    assert t(SanitizeRule(), "a<b>c:d") == "a_b_c_d.mp4"
    assert t(SanitizeRule(), "CON") == "_CON.mp4"

def test_trim_and_truncate():
    from ultrarename.engine import TrimRule, TruncateRule
    assert t(TrimRule(), "  name. ") == "name.mp4"
    out = t(TruncateRule(max_len=10), "averyveryverylongname")
    assert len(out.replace(".mp4", "")) <= 10 and out.endswith(".mp4")

def test_renumber():
    from ultrarename.engine import RenumberRule
    ctx = FileContext(index=2)
    stem, _ = RenumberRule(start=1, step=1, pad=4).transform("ep12 extra", "mkv", ctx)
    assert stem == "ep0003 extra"

def test_random_and_hash():
    from ultrarename.engine import RandomNameRule
    import re as _re
    out = t(RandomNameRule("random", 8), "whatever")
    assert _re.fullmatch(r"[a-z0-9]{8}\.mp4", out)
    out2 = t(RandomNameRule("md5", 12), "whatever")
    assert _re.fullmatch(r"[0-9a-f]{12}\.mp4", out2)

def test_folder_name(tmp_path):
    from ultrarename.engine import FolderNameRule, Pipeline
    d = tmp_path / "资料库"; d.mkdir()
    f = d / "a.txt"; f.write_text("x")
    items = Pipeline([FolderNameRule("prefix", " - ")]).preview([str(f)])
    assert Pipeline.new_name(items[0]) == "资料库 - a.txt"

def test_split_reorder():
    from ultrarename.engine import SplitReorderRule
    assert t(SplitReorderRule(" - ", "2,1"), "Artist - Title") == "Title - Artist.mp4"

def test_media_tag_fallback_no_mutagen():
    from ultrarename.engine import MediaTagRule
    # 无 mutagen 或无法读取时应原样保留
    assert t(MediaTagRule("{title}"), "fallback") == "fallback.mp4"

def test_folderize_date_and_name():
    from ultrarename.engine import FolderizeRule, RenameItem
    item = RenameItem(
        "clip", "mp4", FileContext(index=0,
        mtime=dt.datetime(2026, 11, 25)))
    FolderizeRule("date", "%Y-%m").run(item)
    assert item.new_subdir == "2026-11"
    item2 = item.__class__("ADN-476 名前", "mp4", item.ctx)
    FolderizeRule("name", "^([A-Z]{2,6}-\\d+)").run(item2)
    assert item2.new_subdir == "ADN-476"

def test_list_rule_and_executor_subdir(tmp_path):
    from ultrarename.engine import ListRule, Pipeline, RenameExecutor
    (tmp_path / "old.txt").write_text("x")
    csvp = tmp_path / "map.csv"
    csvp.write_text("old.txt,子目录/new.txt\n", encoding="utf-8")
    items = Pipeline([ListRule(str(csvp))]).preview([str(tmp_path / "old.txt")])
    assert items[0].new_subdir == "子目录"
    done, failed = RenameExecutor(None).execute(items, base_dir=str(tmp_path))
    assert not failed and (tmp_path / "子目录" / "new.txt").exists()

def test_csv_roundtrip(tmp_path):
    import csv as _csv
    from ultrarename.engine import Pipeline, ReplaceRule
    files = ["/demo/a.mp4", "/demo/b.mp4"]
    p = Pipeline([ReplaceRule("a", "x")])
    items = p.preview(files)
    out = tmp_path / "m.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = _csv.writer(f)
        for it in items:
            w.writerow([p.old_name(it), p.new_name(it)])
    rows = list(_csv.reader(open(out, encoding="utf-8-sig")))
    assert rows == [["a.mp4", "x.mp4"], ["b.mp4", "b.mp4"]]

# --- 插入
def test_insert_prefix_suffix_index():
    assert t(InsertRule("new_", "prefix"), "name") == "new_name.mp4"
    assert t(InsertRule("_old", "suffix"), "name") == "name_old.mp4"
    assert t(InsertRule("-", "index", index=3), "abcdef") == "abc-def.mp4"

def test_insert_after_char():
    assert t(InsertRule("(完)", "after_char", char="]"), "x]名") == "x](完)名.mp4"

def test_insert_include_ext():
    assert t(InsertRule("_hd", "suffix", include_ext=True), "name", "mp4") == "name_hd.mp4"

# --- 编号
def test_number_prefix_padded():
    ctx = FileContext(index=2)
    stem, ext = NumberRule(start=1, step=1, pad=4).transform("name", "mp4", ctx)
    assert (stem, ext) == ("0003 name", "mp4")

def test_number_suffix_step5():
    stem, _ = NumberRule(start=10, step=5, pad=2, mode="suffix", sep="-").transform("n", "", FileContext(index=3))
    assert stem == "n-25"

# --- 日期
def test_date_mtime():
    assert t(DateRule("mtime", "%Y%m%d"), "clip") == "20261125 clip.mp4"

def test_date_suffix_today():
    assert t(DateRule("today", "%Y-%m-%d", mode="suffix", sep="_"), "clip") == "clip_2026-11-25.mp4"

# --- 移动/交换
def test_move_first_n_to_end():
    assert t(MoveSwapRule("first_n_to_end", n=3), "abcdef") == "defabc.mp4"

def test_move_last_n_to_start():
    assert t(MoveSwapRule("last_n_to_start", n=2), "abcdef") == "efabcd.mp4"

def test_swap_words():
    assert t(MoveSwapRule("swap_words"), "歌手 名前") == "名前 歌手.mp4"

# --- 裁剪
def test_crop_n():
    assert t(CropRule(n=4, keep="first"), "abcdef") == "abcd.mp4"
    assert t(CropRule(n=4, keep="last"), "abcdef") == "cdef.mp4"

def test_crop_sep():
    r = CropRule(sep=" ", side="before", keep="first")
    assert t(r, "ADN-476 お父さん、ごめんね。") == "ADN-476.mp4"

# --- 扩展名
def test_ext_set_remove_case():
    assert t(ExtRule("set", "mkv"), "a", "mp4") == "a.mkv"
    assert t(ExtRule("remove"), "a", "mp4") == "a"
    assert t(ExtRule("upper"), "a", "mp4") == "a.MP4"

# --- 脚本
def test_script_rule():
    code = "def rename(stem, ext, ctx):\n    return stem.upper(), ext"
    assert t(ScriptRule(code), "abc") == "ABC.mp4"

def test_script_rule_bad():
    with pytest.raises(ValueError):
        ScriptRule("def nope(): pass")

# --- 管道
def test_pipeline_chain_and_preview(tmp_path):
    for n in ["aaa1.txt", "aaa2.txt"]:
        (tmp_path / n).write_text("x")
    p = Pipeline([ReplaceRule("aaa", "bbb"), NumberRule(1, 1, 2, "prefix", "-")])
    items = p.preview([str(tmp_path / n) for n in ["aaa1.txt", "aaa2.txt"]])
    names = [p.new_name(i) for i in items]
    assert names == ["01-bbb1.txt", "02-bbb2.txt"]

def test_pipeline_conflict_detection(tmp_path):
    for n in ["a.txt", "b.txt"]:
        (tmp_path / n).write_text("x")
    p = Pipeline([RegexRule(r"^[ab]$", "same")])
    items = p.preview([str(tmp_path / n) for n in ["a.txt", "b.txt"]])
    assert p.conflicts(items) == {"same.txt": ["a.txt", "b.txt"]}

def test_pipeline_disabled_rule_skipped():
    r = ReplaceRule("a", "X")
    r.enabled = False
    p = Pipeline([r])
    items = p.preview(["/fake/aaa.txt"])
    assert p.new_name(items[0]) == "aaa.txt"
