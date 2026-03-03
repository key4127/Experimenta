#!/usr/bin/env python3
"""
删除「已有对应 doc」的本地仓库目录，用于在生成文档后释放磁盘。

逻辑：扫描 docs 目录（默认 tmp/generate_docs）中的成功 doc 文件（*.json 且非 *_error.json），
根据文件名推导出 repo 目录名（与 batch_clone_repos / batch_generate_docs 一致），
在 repo-dir 下删除对应目录。

用法:
  python -m scripts.doc_agent.clean_repos_with_docs [--docs-dir DIR] [--repo-dir DIR] [--dry-run]
  python -m scripts.doc_agent.clean_repos_with_docs --dry-run   # 仅打印将删除的目录，不实际删除
"""

import argparse
import shutil
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def collect_doc_stems(docs_dir: Path) -> list[str]:
    """
    收集 docs_dir 下「成功」的 doc 文件名（去掉 .json）作为 repo 目录名。
    成功 = 以 .json 结尾且不以 _error.json 结尾，且可视为有效 doc（可选：含 "docs" 键）。
    """
    stems: list[str] = []
    if not docs_dir.is_dir():
        return stems
    for path in docs_dir.glob("*.json"):
        if path.name.endswith("_error.json"):
            continue
        stem = path.stem  # 如 owner_repo
        stems.append(stem)
    return stems


def main() -> None:
    parser = argparse.ArgumentParser(
        description="删除已有对应 doc 的本地仓库目录，释放磁盘",
        epilog="用法: python -m scripts.doc_agent.clean_repos_with_docs [--docs-dir DIR] [--repo-dir DIR] [--dry-run]",
    )
    parser.add_argument(
        "--docs-dir", "-d",
        type=Path,
        default=PROJECT_ROOT / "tmp" / "generate_docs",
        help="doc 输出目录（默认 tmp/generate_docs）",
    )
    parser.add_argument(
        "--repo-dir", "-r",
        type=Path,
        default=PROJECT_ROOT / "repo",
        help="本地仓库根目录（默认 repo/）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印将删除的目录，不实际删除",
    )
    args = parser.parse_args()

    docs_dir = args.docs_dir.resolve()
    repo_dir = args.repo_dir.resolve()

    stems = collect_doc_stems(docs_dir)
    if not stems:
        print(f"在 {docs_dir} 下未找到有效 doc 文件（*.json 且非 *_error.json）。", file=sys.stderr)
        return

    to_remove: list[Path] = []
    for stem in stems:
        candidate = repo_dir / stem
        if candidate.is_dir() and any(candidate.iterdir()):
            to_remove.append(candidate)

    if not to_remove:
        print("没有需要删除的仓库目录（doc 对应的目录在 repo-dir 中不存在或为空）。")
        return

    print(f"共 {len(to_remove)} 个仓库目录已有对应 doc，将{'（dry-run）' if args.dry_run else ''}删除：")
    for p in sorted(to_remove):
        print(f"  {p}")

    if args.dry_run:
        print("未实际删除（使用了 --dry-run）。")
        return

    failed: list[tuple[Path, str]] = []
    for p in to_remove:
        try:
            shutil.rmtree(p)
        except Exception as e:
            failed.append((p, str(e)))

    if failed:
        print("删除失败：", file=sys.stderr)
        for p, err in failed:
            print(f"  {p}: {err}", file=sys.stderr)
        sys.exit(1)
    print(f"已删除 {len(to_remove)} 个目录。")


if __name__ == "__main__":
    main()
