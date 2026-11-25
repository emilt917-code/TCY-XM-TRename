# TRename

BRU（Bulk Rename Utility）全量复刻 + 超越的批量重命名工具。Python + PySide6，跨平台（macOS / Windows）。

## 功能（26 类规则）

**字符类**：正则替换（捕获组）、替换文本（大小写/全词/仅首）、大小写 ×4 模式（例外词表）
**删除类**：前 n / 后 n / 区间 / 前缀后缀 / 括号内容 / 字符集·数字·符号·双空格 / 全角→半角 NFKC / 跨平台净化 / 修剪首尾 / 限制最大长度
**插入类**：任意位置 / 前后缀 / 定位字符 / 自动编号（起始·步长·补零）/ 重编号（替换已有数字）/ 随机·哈希命名 / 日期 ×4 来源
**结构类**：移动交换 / 拆分重排 / 裁剪 / 扩展名操作 / 注入父文件夹名 / 归档子目录 folderize（按日期或正则）
**外部类**：媒体标签（MP3/MP4 内嵌信息，mutagen）/ CSV 映射导入导出 / Python 脚本钩子

**安全性**：预览列实时刷新、批内重名冲突检测、覆盖预警并阻止执行、JSONL 撤销日志按批回滚、dry-run。

## 运行

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip ...
PYTHONPATH=. .venv/bin/python run.py
```

## 打包

- macOS：`.venv/bin/pyinstaller --onefile --windowed --name UltraRename run.py` → `dist/UltraRename.app`
- Windows：双击 `build_win.bat`（用阿里云镜像装依赖）→ `dist/UltraRename.exe`

## 测试

```bash
.venv/bin/python -m pytest tests/ -q
```

## 目录结构

- `ultrarename/engine/` 规则引擎（rules/pipeline/executor），纯逻辑，GUI 无关
- `ultrarename/gui/` PySide6 界面（main_window / rules_panel / rule_card / rule_specs）
- `tests/` 46 项单元测试
- `scripts/screenshot.py` 离屏截图自检
