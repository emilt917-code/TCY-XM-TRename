"""规则类型声明：GUI 卡片与引擎规则的桥梁（schema 驱动）。"""
from __future__ import annotations

from ultrarename.engine import (
    CaseRule, CropRule, DateRule, ExtRule, FolderNameRule, FolderizeRule,
    InsertRule, ListRule, MediaTagRule, MoveSwapRule, NormalizeRule,
    NumberRule, RandomNameRule, RegexRule, RemoveAffix, RemoveCharset,
    RemoveFirstN, RemoveLastN, RemoveRange, RenumberRule, ReplaceRule,
    SanitizeRule, ScriptRule, SplitReorderRule, StripBrackets, TrimRule,
    TruncateRule,
)

# 字段类型: text / int / check / combo / code
SPEC = {
    "RegexRule": {
        "label": "① 正则替换",
        "fields": [
            ("match", "匹配", "text", ""),
            ("replace", "替换为", "text", ""),
            ("include_ext", "含扩展名", "check", False),
        ],
        "factory": lambda p: RegexRule(p["match"], p["replace"],
                                       p.get("include_ext", False)),
    },
    "CaseRule": {
        "label": "② 大小写",
        "fields": [
            ("mode", "模式", "combo", "upper",
             ["upper", "lower", "title", "sentence"]),
            ("exceptions", "例外词(逗号分隔)", "text", ""),
        ],
        "factory": lambda p: CaseRule(
            p["mode"], [w.strip() for w in p.get("exceptions", "").split(",") if w.strip()]),
    },
    "ReplaceRule": {
        "label": "③ 替换文本",
        "fields": [
            ("find", "查找", "text", ""),
            ("replace", "替换为", "text", ""),
            ("case_sensitive", "区分大小写", "check", True),
            ("whole_word", "全词匹配", "check", False),
            ("first_only", "仅首个", "check", False),
        ],
        "factory": lambda p: ReplaceRule(p["find"], p["replace"],
                                         p.get("case_sensitive", True),
                                         p.get("whole_word", False),
                                         p.get("first_only", False)),
    },
    "RemoveFirstN": {
        "label": "④a 删除前 n 字符",
        "fields": [("n", "n", "int", 1)],
        "factory": lambda p: RemoveFirstN(p["n"]),
    },
    "RemoveLastN": {
        "label": "④b 删除后 n 字符",
        "fields": [("n", "n", "int", 1)],
        "factory": lambda p: RemoveLastN(p["n"]),
    },
    "RemoveRange": {
        "label": "④c 删除区间字符",
        "fields": [("start", "起始(1起)", "int", 2), ("end", "结束(含)", "int", 4)],
        "factory": lambda p: RemoveRange(p["start"], p["end"]),
    },
    "RemoveAffix": {
        "label": "④e 删除前缀/后缀",
        "fields": [
            ("text", "内容", "text", ""),
            ("mode", "类型", "combo", "suffix", ["suffix", "prefix"]),
            ("all_occurrences", "连续重复都删", "check", False),
        ],
        "factory": lambda p: RemoveAffix(p["text"], p["mode"],
                                         p.get("all_occurrences", False)),
    },
    "StripBrackets": {
        "label": "④f 删除括号内容",
        "fields": [
            ("kinds", "括号类型(逗号分隔,留空=全部)", "text", ""),
            ("keep_marks", "保留空括号", "check", False),
            ("collapse_spaces", "合并多空格", "check", True),
        ],
        "factory": lambda p: StripBrackets(
            [k.strip() for k in p["kinds"].split(",") if len(k.strip()) == 2]
            if p["kinds"].strip() else None,
            p.get("keep_marks", False), p.get("collapse_spaces", True)),
    },
    "NormalizeRule": {
        "label": "④g 全角→半角规范化",
        "fields": [("to_halfwidth", "启用 NFKC", "check", True)],
        "factory": lambda p: NormalizeRule(p.get("to_halfwidth", True)),
    },
    "SanitizeRule": {
        "label": "④h 跨平台净化（去非法字符）",
        "fields": [("replace_with", "替换为", "text", "_")],
        "factory": lambda p: SanitizeRule(p["replace_with"]),
    },
    "TrimRule": {
        "label": "④i 修剪首尾空白/点",
        "fields": [],
        "factory": lambda p: TrimRule(),
    },
    "TruncateRule": {
        "label": "④j 限制最大长度",
        "fields": [("max_len", "最大字符数", "int", 120)],
        "factory": lambda p: TruncateRule(p["max_len"]),
    },
    "RemoveCharset": {
        "label": "④d 删除字符集",
        "fields": [
            ("chars", "指定字符", "text", ""),
            ("digits", "删除数字", "check", False),
            ("symbols", "删除符号", "check", False),
            ("double_spaces", "合并双空格", "check", False),
        ],
        "factory": lambda p: RemoveCharset(p["chars"], p.get("digits", False),
                                           p.get("symbols", False),
                                           p.get("double_spaces", False)),
    },
    "InsertRule": {
        "label": "⑤ 插入文本",
        "fields": [
            ("text", "文本", "text", ""),
            ("mode", "位置", "combo", "prefix",
             ["prefix", "suffix", "index", "after_char", "before_char"]),
            ("index", "位置序号(1起,0=末尾)", "int", 0),
            ("char", "定位字符", "text", ""),
            ("include_ext", "定位含扩展名", "check", False),
        ],
        "factory": lambda p: InsertRule(p["text"], p["mode"], p["index"],
                                        p["char"], p.get("include_ext", False)),
    },
    "NumberRule": {
        "label": "⑥ 自动编号",
        "fields": [
            ("start", "起始", "int", 1),
            ("step", "步长", "int", 1),
            ("pad", "位数补零", "int", 3),
            ("mode", "位置", "combo", "prefix", ["prefix", "suffix"]),
            ("sep", "分隔符", "text", " "),
        ],
        "factory": lambda p: NumberRule(p["start"], p["step"], p["pad"],
                                        p["mode"], p["sep"]),
    },
    "DateRule": {
        "label": "⑦ 插入日期",
        "fields": [
            ("source", "来源", "combo", "mtime",
             ["mtime", "atime", "ctime", "today"]),
            ("fmt", "格式(%Y-%m-%d)", "text", "%Y-%m-%d"),
            ("mode", "位置", "combo", "prefix", ["prefix", "suffix"]),
            ("sep", "分隔符", "text", " "),
        ],
        "factory": lambda p: DateRule(p["source"], p["fmt"], p["mode"], p["sep"]),
    },
    "MoveSwapRule": {
        "label": "⑧ 移动/交换",
        "fields": [
            ("mode", "模式", "combo", "swap_words",
             ["first_n_to_end", "last_n_to_start", "swap_words"]),
            ("n", "n 字符", "int", 0),
            ("sep", "词分隔符", "text", " "),
        ],
        "factory": lambda p: MoveSwapRule(p["mode"], p["n"], p["sep"]),
    },
    "CropRule": {
        "label": "⑨ 裁剪",
        "fields": [
            ("n", "保留 n 字符", "int", 0),
            ("keep", "保留哪端", "combo", "first", ["first", "last"]),
            ("sep", "按分隔符裁剪(优先)", "text", ""),
            ("side", "分隔符匹配", "combo", "before", ["before", "after"]),
        ],
        "factory": lambda p: CropRule(p["n"], p["keep"], p["sep"], p["side"]),
    },
    "ExtRule": {
        "label": "⑩ 扩展名",
        "fields": [
            ("mode", "操作", "combo", "lower",
             ["set", "remove", "lower", "upper"]),
            ("new_ext", "新扩展名(set)", "text", ""),
        ],
        "factory": lambda p: ExtRule(p["mode"], p["new_ext"]),
    },
    "RenumberRule": {
        "label": "⑥b 重编号（替换已有数字）",
        "fields": [
            ("start", "起始", "int", 1),
            ("step", "步长", "int", 1),
            ("pad", "位数补零", "int", 3),
        ],
        "factory": lambda p: RenumberRule(p["start"], p["step"], p["pad"]),
    },
    "RandomNameRule": {
        "label": "⑥c 随机/哈希命名",
        "fields": [
            ("mode", "模式", "combo", "random",
             ["random", "md5", "sha1", "sha256"]),
            ("length", "长度", "int", 8),
        ],
        "factory": lambda p: RandomNameRule(p["mode"], p["length"]),
    },
    "FolderNameRule": {
        "label": "⑦b 注入父文件夹名",
        "fields": [
            ("mode", "位置", "combo", "prefix", ["prefix", "suffix"]),
            ("sep", "分隔符", "text", " - "),
        ],
        "factory": lambda p: FolderNameRule(p["mode"], p["sep"]),
    },
    "SplitReorderRule": {
        "label": "⑧b 拆分重排（如 2,1 交换两段）",
        "fields": [
            ("sep", "分隔符", "text", " - "),
            ("order", "顺序(段号,如 2,1)", "text", "2,1"),
            ("joiner", "连接符", "text", " - "),
        ],
        "factory": lambda p: SplitReorderRule(p["sep"], p["order"], p["joiner"]),
    },
    "MediaTagRule": {
        "label": "⑫ 媒体标签（MP3/MP4 标题等）",
        "fields": [("template", "模板 {title} {artist} {album} {date}",
                    "text", "{artist} - {title}")],
        "factory": lambda p: MediaTagRule(p["template"]),
    },
    "FolderizeRule": {
        "label": "⑬ 归档到子目录（folderize）",
        "fields": [
            ("mode", "模式", "combo", "date", ["date", "name"]),
            ("pattern", "date=日期格式 / name=正则", "text", "%Y-%m"),
        ],
        "factory": lambda p: FolderizeRule(p["mode"], p["pattern"]),
    },
    "ListRule": {
        "label": "⑭ CSV 映射重命名",
        "fields": [("csv_path", "CSV 路径（两列：原名,新名）", "text", "")],
        "factory": lambda p: ListRule(p["csv_path"]),
    },
    "ScriptRule": {
        "label": "⑪ Python 脚本钩子",
        "fields": [
            ("code", "代码（需定义 rename(stem, ext, ctx)）", "code",
             "def rename(stem, ext, ctx):\n    return stem, ext"),
        ],
        "factory": lambda p: ScriptRule(p["code"]),
    },
}

ORDER = ["RegexRule", "ReplaceRule", "CaseRule", "RemoveFirstN", "RemoveLastN",
         "RemoveRange", "RemoveAffix", "StripBrackets", "NormalizeRule",
         "SanitizeRule", "TrimRule", "TruncateRule", "RemoveCharset",
         "InsertRule", "NumberRule", "RenumberRule", "RandomNameRule",
         "DateRule", "FolderNameRule", "MoveSwapRule", "SplitReorderRule",
         "CropRule", "ExtRule", "MediaTagRule", "FolderizeRule", "ListRule",
         "ScriptRule"]


def defaults(rule_type: str) -> dict:
    return {name: default for name, _l, _t, default in SPEC[rule_type]["fields"]}
