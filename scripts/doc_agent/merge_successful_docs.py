"""
将指定目录中所有成功内容（含 docs 或旧键「概括仓库内容」的 JSON）合并为一个 JSON 文件，
统一使用键 docs。

支持两种格式：
- 默认：每个文件为单个对象，且含 docs/概括仓库内容 键。
- --format structured：每个文件为「对象数组」，每项含 docs（如 data/structured 下的 JSON）。

用法:
  python -m scripts.doc_agent.merge_successful_docs [--input DIR] [--output FILE]
  python -m scripts.doc_agent.merge_successful_docs --input scripts/doc_agent/output --output data/raw/merged_docs.json
  python -m scripts.doc_agent.merge_successful_docs --format structured -i data/structured -o data/merged_structured.json
"""
import argparse
import json
from pathlib import Path

# 本脚本所在目录与项目根
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DOC_KEYS = ("docs", "概括仓库内容")


def merge_structured_docs(input_dir: Path, out_path: Path) -> int:
    """
    合并「数组格式」的 JSON：目录下每个 .json 文件均为 list，
    每项为含 docs（及如 repo_url 等）的对象，将所有数组合并为一个 JSON 数组写出。

    :param input_dir: 存放多个 .json 的目录
    :param out_path: 合并后的输出 JSON 路径
    :return: 合并后的总条数
    """
    input_dir = input_dir.resolve()
    out_path = out_path.resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"目录不存在: {input_dir}")

    results: list[dict] = []
    for path in sorted(input_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"跳过 {path.name}: 读取失败 {e}")
            continue

        if not isinstance(obj, list):
            print(f"跳过 {path.name}: 非数组格式 (type={type(obj).__name__})")
            continue

        for i, item in enumerate(obj):
            if not isinstance(item, dict):
                continue
            if "docs" in item or "概括仓库内容" in item:
                entry = dict(item)
                if "概括仓库内容" in entry and "docs" not in entry:
                    entry["docs"] = entry.pop("概括仓库内容")
                results.append(entry)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return len(results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="合并成功生成的文档 JSON 为单个文件")
    parser.add_argument(
        "--format", "-f",
        choices=["single", "structured"],
        default="single",
        help="single: 每文件一个对象且含 docs；structured: 每文件为对象数组 (如 data/structured)",
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=SCRIPT_DIR / "output",
        help="待合并的 JSON 所在目录，默认 scripts/doc_agent/output",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "iclr_papers_2024_docs.json",
        help="合并后的输出 JSON 路径，默认 data/raw/iclr_papers_2024_docs.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = args.input.resolve()
    out_path = args.output.resolve()

    if args.format == "structured":
        try:
            n = merge_structured_docs(input_dir, out_path)
            print(f"已合并 {n} 条成功记录 -> {out_path}")
        except FileNotFoundError as e:
            print(e)
        return

    if not input_dir.is_dir():
        print(f"输出目录不存在: {input_dir}")
        return

    results: list[dict] = []
    for path in sorted(input_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"跳过 {path.name}: 读取失败 {e}")
            continue

        if not isinstance(obj, dict):
            continue
        doc_key = next((k for k in DOC_KEYS if k in obj), None)
        if doc_key is None:
            continue

        # 复制条目，统一使用键 docs
        entry = {}
        for k, v in obj.items():
            if k in DOC_KEYS:
                entry["docs"] = v
            else:
                entry[k] = v
        results.append(entry)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"已合并 {len(results)} 条成功记录 -> {out_path}")


if __name__ == "__main__":
    main()
