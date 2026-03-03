"""
将指定目录中所有成功内容（含 docs 或旧键「概括仓库内容」的 JSON）合并为一个 JSON 文件，
统一使用键 docs。

用法:
  python -m scripts.doc_agent.merge_successful_docs [--input DIR] [--output FILE]
  python -m scripts.doc_agent.merge_successful_docs --input scripts/doc_agent/output --output data/raw/merged_docs.json
"""
import argparse
import json
from pathlib import Path

# 本脚本所在目录与项目根
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

DOC_KEYS = ("docs", "概括仓库内容")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="合并成功生成的文档 JSON 为单个文件")
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
