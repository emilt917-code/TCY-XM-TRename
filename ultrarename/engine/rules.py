"""UltraRename 规则引擎核心。

所有规则以 (stem, ext) 二元组为输入输出，ext 不含点。
每条规则只变换文件名主部，除非显式声明处理扩展名。
"""
from __future__ import annotations

import datetime as _dt
import csv
import hashlib
import os
import random
import string
import unicodedata
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FileContext:
    """单个文件在重命名时可供规则使用的上下文信息。"""
    index: int = 0                 # 当前文件在本次批处理中的序号（0 起）
    path: str = ""                 # 原始完整路径
    size: int = 0                  # 字节
    mtime: _dt.datetime | None = None   # 修改时间
    atime: _dt.datetime | None = None   # 访问时间
    ctime: _dt.datetime | None = None   # 创建/变更时间
    today: _dt.datetime = field(default_factory=_dt.datetime.now)


@dataclass
class RenameItem:
    """待重命名文件：old 为当前名，new 由管道计算。"""
    stem: str
    ext: str
    ctx: FileContext
    new_stem: str = ""
    new_ext: str = ""
    new_subdir: str = ""   # folderize：目标子目录（相对当前目录）


class Rule(ABC):
    """规则基类。enabled=False 的规则在管道中被跳过。"""
    name: str = "rule"
    enabled: bool = True

    @abstractmethod
    def transform(self, stem: str, ext: str, ctx: FileContext) -> tuple[str, str]:
        ...

    def run(self, item: RenameItem) -> None:
        if not self.enabled:
            return
        item.new_stem, item.new_ext = self.transform(
            item.new_stem or item.stem, item.new_ext or item.ext, item.ctx
        )


def _title_word(w: str) -> str:
    if not w:
        return w
    return w[0].upper() + w[1:]


# ---------------------------------------------------------------- 正则
class RegexRule(Rule):
    """正则替换。replace 支持 \\1..\\n 反向引用。"""
    name = "regex"

    def __init__(self, match: str, replace: str = "", include_ext: bool = False,
                 flags: int = 0):
        self.match = match
        self.replace = replace
        self.include_ext = include_ext
        self.flags = flags

    def transform(self, stem, ext, ctx):
        if not self.match:
            return stem, ext
        if self.include_ext:
            target = f"{stem}.{ext}" if ext else stem
            out = re.sub(self.match, self.replace, target, flags=self.flags)
            stem2, _, ext2 = out.rpartition(".")
            if stem2 == "" and "." not in out:
                return out, ""
            return (stem2, ext2) if ext else (out, "")
        return re.sub(self.match, self.replace, stem, flags=self.flags), ext


# ---------------------------------------------------------------- 大小写
class CaseRule(Rule):
    """upper/lower/title/sentence，exceptions 为保持原样的词表。"""
    name = "case"
    MODES = ("upper", "lower", "title", "sentence")

    def __init__(self, mode: str, exceptions: list[str] | None = None):
        assert mode in self.MODES
        self.mode = mode
        self.exceptions = [e for e in (exceptions or []) if e]

    def _apply(self, text: str) -> str:
        if self.mode == "upper":
            return text.upper()
        if self.mode == "lower":
            return text.lower()
        if self.mode == "title":
            parts = re.split(r"(\s+)", text)
            return "".join(
                p if not p.strip() or p.lower() in
                {e.lower() for e in self.exceptions} else _title_word(p)
                for p in parts
            )
        # sentence: 整段首字母大写，其余小写；例外词保持原样
        low = text.lower()
        out = low[:1].upper() + low[1:]
        for e in self.exceptions:
            out = re.sub(re.escape(e), e, out, flags=re.IGNORECASE)
        return out

    def transform(self, stem, ext, ctx):
        return self._apply(stem), ext


# ---------------------------------------------------------------- 替换
class ReplaceRule(Rule):
    name = "replace"

    def __init__(self, find: str, replace: str = "", case_sensitive: bool = True,
                 whole_word: bool = False, first_only: bool = False):
        self.find = find
        self.replace = replace
        self.case_sensitive = case_sensitive
        self.whole_word = whole_word
        self.first_only = first_only

    def transform(self, stem, ext, ctx):
        if not self.find:
            return stem, ext
        pattern = re.escape(self.find)
        if self.whole_word:
            pattern = rf"\b(?:{pattern})\b"
        count = 1 if self.first_only else 0
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.sub(pattern, self.replace.replace("\\", "\\\\"), stem,
                      count=count, flags=flags), ext


# ---------------------------------------------------------------- 移除
class RemoveFirstN(Rule):
    name = "remove_first_n"

    def __init__(self, n: int):
        self.n = max(0, n)

    def transform(self, stem, ext, ctx):
        return stem[self.n:], ext


class RemoveLastN(Rule):
    name = "remove_last_n"

    def __init__(self, n: int):
        self.n = max(0, n)

    def transform(self, stem, ext, ctx):
        return stem[:len(stem) - self.n] if self.n else stem, ext


class RemoveRange(Rule):
    """删除第 start 个到第 end 个字符（1 起，含端点）。"""
    name = "remove_range"

    def __init__(self, start: int, end: int):
        self.start = max(1, start)
        self.end = max(self.start, end)

    def transform(self, stem, ext, ctx):
        return stem[:self.start - 1] + stem[self.end:], ext


class RemoveCharset(Rule):
    name = "remove_charset"

    def __init__(self, chars: str = "", digits: bool = False, symbols: bool = False,
                 double_spaces: bool = False):
        self.chars = chars
        self.digits = digits
        self.symbols = symbols
        self.double_spaces = double_spaces

    def transform(self, stem, ext, ctx):
        out = stem
        if self.chars:
            out = out.translate({ord(c): None for c in self.chars})
        if self.digits:
            out = re.sub(r"\d", "", out)
        if self.symbols:
            out = re.sub(r"[^\w\s]", "", out, flags=re.UNICODE)
        if self.double_spaces:
            while "  " in out:
                out = out.replace("  ", " ")
        return out, ext


class RemoveAffix(Rule):
    """删除指定前缀/后缀（存在才删，默认只删一次）。"""
    name = "remove_affix"

    def __init__(self, text: str, mode: str = "suffix", all_occurrences: bool = False):
        self.text = text
        self.mode = mode  # prefix / suffix
        self.all_occurrences = all_occurrences

    def transform(self, stem, ext, ctx):
        if not self.text:
            return stem, ext
        if self.mode == "prefix":
            while stem.startswith(self.text):
                stem = stem[len(self.text):]
                if not self.all_occurrences:
                    break
        else:
            while stem.endswith(self.text):
                stem = stem[:len(stem) - len(self.text)]
                if not self.all_occurrences:
                    break
        return stem, ext


# ---------------------------------------------------------------- 括号/标签清理
class StripBrackets(Rule):
    """删除括号及其内容。支持 () [] {} 【】《》〈〉等，可选保留括号本身。"""
    name = "strip_brackets"

    PAIRS = [("(", ")"), ("[", "]"), ("{", "}"), ("【", "】"),
             ("《", "》"), ("〈", "〉"), ("［", "］"), ("（", "）")]

    def __init__(self, kinds: list | None = None, keep_marks: bool = False,
                 collapse_spaces: bool = True):
        norm = []
        for k in (kinds if kinds else self.PAIRS):
            if isinstance(k, str) and len(k) == 2:
                k = (k[0], k[1])
            norm.append(tuple(k))
        self.kinds = tuple(norm)
        self.keep_marks = keep_marks
        self.collapse_spaces = collapse_spaces

    def transform(self, stem, ext, ctx):
        out = stem
        for pair in self.kinds:
            o, c = pair
            pattern = re.escape(o) + r".*?" + re.escape(c)
            repl = (o + c) if self.keep_marks else ""
            out = re.sub(pattern, repl, out, flags=re.DOTALL)
        if self.collapse_spaces:
            out = re.sub(r"\s{2,}", " ", out).strip()
        return out, ext


# ---------------------------------------------------------------- 规范化
class NormalizeRule(Rule):
    """NFKC 规范化：全角字母数字/符号→半角等。可选简化空白。"""
    name = "normalize"

    def __init__(self, to_halfwidth: bool = True):
        self.to_halfwidth = to_halfwidth

    def transform(self, stem, ext, ctx):
        out = unicodedata.normalize("NFKC", stem) if self.to_halfwidth else stem
        out = re.sub(r"\s{2,}", " ", out).strip()
        return out, ext


class SanitizeRule(Rule):
    """净化为跨平台安全文件名：去除 Windows 非法字符/保留名/首尾点空格。"""
    name = "sanitize"

    ILLEGAL = r'[\\/:*?"<>|]'
    RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}

    def __init__(self, replace_with: str = "_"):
        self.replace_with = replace_with

    def transform(self, stem, ext, ctx):
        out = re.sub(self.ILLEGAL, self.replace_with, stem)
        out = out.rstrip(" .")
        if out.upper() in self.RESERVED:
            out = self.replace_with + out
        return out, ext


class TrimRule(Rule):
    """修剪首尾空白/点。"""
    name = "trim"

    def transform(self, stem, ext, ctx):
        return stem.strip(" \t.＿"), ext


class TruncateRule(Rule):
    """限制文件名最大长度（保留扩展名，超长截断主部，可选加序号后缀防重名）。"""
    name = "truncate"

    def __init__(self, max_len: int = 120):
        self.max_len = max(1, max_len)

    def transform(self, stem, ext, ctx):
        budget = self.max_len - (len(ext) + 1 if ext else 0)
        if len(stem) <= budget:
            return stem, ext
        n = str(ctx.index + 1)
        cut = stem[:max(1, budget - len(n) - 1)]
        return f"{cut}~{n}", ext


class RenumberRule(Rule):
    """重编号：找到文件名中最后一串数字，按新起始/步长/位数替换。
    keep_name=True 时仅规范位数不改变数值。"""
    name = "renumber"

    def __init__(self, start: int = 1, step: int = 1, pad: int = 3):
        self.start = start
        self.step = step
        self.pad = pad

    def transform(self, stem, ext, ctx):
        matches = list(re.finditer(r"\d+", stem))
        if not matches:
            return stem, ext
        m = matches[-1]
        new_num = str(self.start + ctx.index * self.step).zfill(self.pad)
        return stem[:m.start()] + new_num + stem[m.end():], ext


class RandomNameRule(Rule):
    """随机/哈希命名：random / md5 / sha1 / sha256。"""
    name = "random_name"

    def __init__(self, mode: str = "random", length: int = 8,
                 keep_ext: bool = True):
        self.mode = mode
        self.length = max(4, length)
        self.keep_ext = keep_ext

    def transform(self, stem, ext, ctx):
        if self.mode == "random":
            alphabet = string.ascii_lowercase + string.digits
            out = "".join(random.choice(alphabet) for _ in range(self.length))
        else:
            h = hashlib.new(self.mode)
            path = ctx.path
            try:
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
            except OSError:
                h.update(path.encode("utf-8", "ignore"))
            out = h.hexdigest()[:self.length]
        return out, ext


class FolderNameRule(Rule):
    """把父文件夹名加进文件名（flatten 目录后保持来源信息）。"""
    name = "folder_name"

    def __init__(self, mode: str = "prefix", sep: str = " - "):
        self.mode = mode
        self.sep = sep

    def transform(self, stem, ext, ctx):
        folder = os.path.basename(os.path.dirname(ctx.path)) if ctx.path else ""
        if not folder:
            return stem, ext
        return (f"{folder}{self.sep}{stem}" if self.mode == "prefix"
                else f"{stem}{self.sep}{folder}"), ext


class SplitReorderRule(Rule):
    """按分隔符拆分后重排/选取：order 如 "2,1" 表示第2段在前、第1段在后。"""
    name = "split_reorder"

    def __init__(self, sep: str = " - ", order: str = "2,1",
                 joiner: str = " - "):
        self.sep = sep
        self.order = [int(x) for x in re.findall(r"\d+", order)]
        self.joiner = joiner

    def transform(self, stem, ext, ctx):
        parts = stem.split(self.sep)
        picked = [parts[i - 1] for i in self.order if 1 <= i <= len(parts)]
        if len(picked) < len(set(self.order)):
            return stem, ext
        return self.joiner.join(picked), ext


class FolderizeRule(Rule):
    """归档：不改名，只算目标子目录。
    mode=date 按日期模板（如 %Y-%m）；mode=name 按正则捕获组命名目录。"""
    name = "folderize"

    def __init__(self, mode: str = "date", pattern: str = "%Y-%m"):
        self.mode = mode
        self.pattern = pattern

    def run(self, item: RenameItem) -> None:
        if not self.enabled:
            return
        if self.mode == "date":
            d = item.ctx.mtime or item.ctx.today
            item.new_subdir = d.strftime(self.pattern)
        else:
            m = re.search(self.pattern, item.new_stem or item.stem)
            if m:
                item.new_subdir = (m.group(1) if m.groups() else m.group(0))
                item.new_subdir = re.sub(r'[\\/:*?"<>|]', "_",
                                         item.new_subdir).strip()

    def transform(self, stem, ext, ctx):  # pragma: no cover - run() 覆盖
        return stem, ext


class ListRule(Rule):
    """CSV 映射重命名：csv 文件两列（原名,新名），命中才改。"""
    name = "list"

    def __init__(self, csv_path: str):
        self.mapping: dict[str, str] = {}
        with open(csv_path, encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                if len(row) >= 2 and row[0] and row[1]:
                    self.mapping[row[0].strip()] = row[1].strip()

    def run(self, item: RenameItem) -> None:
        if not self.enabled:
            return
        old = f"{item.stem}.{item.ext}" if item.ext else item.stem
        target = self.mapping.get(old)
        if not target:
            return
        target = target.replace("\\", "/")
        item.new_subdir = os.path.dirname(target) or ""
        base = os.path.basename(target)
        item.new_stem, _, item.new_ext = base.rpartition(".")
        if not item.new_stem:
            item.new_stem, item.new_ext = base, ""

    def transform(self, stem, ext, ctx):  # pragma: no cover
        return stem, ext


class MediaTagRule(Rule):
    """媒体标签命名：视频/音频取标题、日期等。依赖 mutagen（可选）。
    template 支持 {title} {artist} {album} {date} {track}。"""
    name = "media_tag"

    def __init__(self, template: str = "{artist} - {title}"):
        self.template = template

    def transform(self, stem, ext, ctx):
        try:
            from mutagen import File as MutagenFile
        except ImportError:
            return stem, ext
        mf = MutagenFile(ctx.path) if ctx.path else None
        if mf is None or not getattr(mf, "tags", None):
            return stem, ext

        def get(*keys):
            for k in keys:
                v = mf.tags.get(k)
                if v:
                    return str(v[0]) if isinstance(v, list) else str(v)
            return ""

        tags = {
            "title": get("©nam", "TIT2", "title"),
            "artist": get("©ART", "TPE1", "artist"),
            "album": get("©alb", "TALB", "album"),
            "date": get("©day", "TDRC", "date")[:10],
            "track": get("trkn", "TRCK", "tracknumber").split("/")[0],
        }
        out = self.template.format(**{k: tags[k] or "" for k in tags})
        out = re.sub(r"[\\/:*?\"<>|]", "_", out).strip()
        return (out if out else stem), ext


# ---------------------------------------------------------------- 插入
class InsertRule(Rule):
    """prefix / suffix / index(1起，0=末尾) / after_char / before_char。"""
    name = "insert"
    MODES = ("prefix", "suffix", "index", "after_char", "before_char")

    def __init__(self, text: str, mode: str = "prefix", index: int = 0,
                 char: str = "", include_ext: bool = False):
        assert mode in self.MODES
        self.text = text
        self.mode = mode
        self.index = index
        self.char = char
        self.include_ext = include_ext

    def transform(self, stem, ext, ctx):
        if self.include_ext and ext and self.mode not in ("prefix", "suffix"):
            # 前缀/后缀永远保持扩展名在末尾；include_ext 仅影响位置类模式
            stem = f"{stem}.{ext}"
            ext = ""
        if self.mode == "prefix":
            out = self.text + stem
        elif self.mode == "suffix":
            out = stem + self.text
        elif self.mode == "index":
            i = min(max(self.index, 0), len(stem))
            out = stem[:i] + self.text + stem[i:]
        elif self.mode == "after_char" and self.char:
            p = stem.find(self.char)
            out = stem if p < 0 else stem[:p + len(self.char)] + self.text + stem[p + len(self.char):]
        else:  # before_char
            p = stem.find(self.char)
            out = stem if p < 0 else stem[:p] + self.text + stem[p:]
        return out, ext


# ---------------------------------------------------------------- 编号
class NumberRule(Rule):
    """自动编号：start 起、step 步长、pad 位补零。基于批处理顺序。"""
    name = "number"

    def __init__(self, start: int = 1, step: int = 1, pad: int = 3,
                 mode: str = "prefix", sep: str = " "):
        self.start = start
        self.step = step
        self.pad = pad
        self.mode = mode  # prefix / suffix
        self.sep = sep

    def transform(self, stem, ext, ctx):
        n = str(self.start + ctx.index * self.step).zfill(self.pad)
        return (f"{n}{self.sep}{stem}" if self.mode == "prefix"
                else f"{stem}{self.sep}{n}"), ext


# ---------------------------------------------------------------- 日期
class DateRule(Rule):
    name = "date"
    SOURCES = ("mtime", "atime", "ctime", "today")

    def __init__(self, source: str = "mtime", fmt: str = "%Y-%m-%d",
                 mode: str = "prefix", sep: str = " "):
        assert source in self.SOURCES
        self.source = source
        self.fmt = fmt
        self.mode = mode
        self.sep = sep

    def _dt(self, ctx: FileContext) -> _dt.datetime:
        return {
            "mtime": ctx.mtime, "atime": ctx.atime, "ctime": ctx.ctime,
        }.get(self.source) or ctx.today

    def transform(self, stem, ext, ctx):
        s = self._dt(ctx).strftime(self.fmt)
        return (f"{s}{self.sep}{stem}" if self.mode == "prefix"
                else f"{stem}{self.sep}{s}"), ext


# ---------------------------------------------------------------- 移动/交换
class MoveSwapRule(Rule):
    """first_n_to_end / last_n_to_start / swap_words(按 sep 分隔的两段交换)。"""
    name = "move_swap"
    MODES = ("first_n_to_end", "last_n_to_start", "swap_words")

    def __init__(self, mode: str, n: int = 0, sep: str = " "):
        assert mode in self.MODES
        self.mode = mode
        self.n = max(0, n)
        self.sep = sep

    def transform(self, stem, ext, ctx):
        if self.mode == "first_n_to_end":
            n = min(self.n, len(stem))
            return stem[n:] + stem[:n], ext
        if self.mode == "last_n_to_start":
            n = min(self.n, len(stem))
            return stem[-n:] + stem[:-n] if n else stem, ext
        parts = stem.split(self.sep)
        if len(parts) >= 2:
            parts[0], parts[-1] = parts[-1], parts[0]
            return self.sep.join(parts), ext
        return stem, ext


# ---------------------------------------------------------------- 裁剪
class CropRule(Rule):
    """keep=first/last 保留前/后 n 个字符；或按分隔符截取 before/after。"""
    name = "crop"

    def __init__(self, n: int = 0, keep: str = "first",
                 sep: str = "", side: str = "before"):
        self.n = max(0, n)
        self.keep = keep
        self.sep = sep
        self.side = side

    def transform(self, stem, ext, ctx):
        if self.sep:
            p = stem.find(self.sep) if self.side == "before" else stem.rfind(self.sep)
            if p < 0:
                return stem, ext
            return (stem[:p] if self.keep == "first" else stem[p + len(self.sep):]), ext
        n = min(self.n, len(stem))
        return (stem[:n] if self.keep == "first" else stem[-n:]) if n else stem, ext


# ---------------------------------------------------------------- 扩展名
class ExtRule(Rule):
    name = "ext"
    MODES = ("set", "remove", "lower", "upper")

    def __init__(self, mode: str = "lower", new_ext: str = ""):
        assert mode in self.MODES
        self.mode = mode
        self.new_ext = new_ext

    def transform(self, stem, ext, ctx):
        if self.mode == "set":
            return stem, self.new_ext
        if self.mode == "remove":
            return stem, ""
        return stem, getattr(ext, self.mode)()


# ---------------------------------------------------------------- 脚本
class ScriptRule(Rule):
    """Python 脚本钩子。代码需定义 def rename(stem, ext, ctx): -> (stem, ext)"""
    name = "script"

    def __init__(self, code: str):
        self.code = code
        ns: dict = {}
        exec(compile(code, "<rename-script>", "exec"), {"__builtins__": __builtins__}, ns)
        fn = ns.get("rename")
        if not callable(fn):
            raise ValueError("script must define rename(stem, ext, ctx)")
        self._fn = fn

    def transform(self, stem, ext, ctx):
        out = self._fn(stem, ext, ctx)
        if not (isinstance(out, tuple) and len(out) == 2):
            raise ValueError("rename() must return (stem, ext)")
        return out
