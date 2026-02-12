"""
创建 code_url 到本地仓库路径的映射。
读取 data/raw 中的 JSON，提取 code_url，生成映射文件供 batch_generate_docstrings 使用。
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_paper_data(data_dir: str) -> List[dict]:
    if not Path(data_dir).is_absolute():
        data_dir = project_root / data_dir
    data_dir = Path(data_dir)
    all_papers = []
    for f in data_dir.glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            all_papers.extend(data if isinstance(data, list) else [data])
    return all_papers


def clone_repo(repo_url: str, dest_dir: Path) -> bool:
    """克隆仓库到 dest_dir 下，以仓库名为子目录。已存在则视为成功。"""
    name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    target = Path(dest_dir) / name
    if target.exists():
        return True
    dest_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target)],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def create_mapping(papers: List[dict], repos_base_dir: str, output_file: str) -> None:
    base = Path(repos_base_dir)
    base.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for paper in papers:
        code_url = paper.get("code_url")
        if not code_url:
            continue
        name = code_url.rstrip("/").split("/")[-1].replace(".git", "")
        local_path = None
        for p in [base / name, base / code_url.split("/")[-2] / name]:
            if p.exists() and p.is_dir():
                local_path = p
                break
        if local_path is None:
            if clone_repo(code_url, base):
                local_path = base / name
        if local_path is not None:
            mapping[code_url] = str(local_path.resolve())
    out = Path(output_file) if Path(output_file).is_absolute() else project_root / output_file
    if out.is_dir():
        out = out / "repo_mapping.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"已写入 {out}，共 {len(mapping)} 条")


def main():
    p = argparse.ArgumentParser(description="生成 code_url -> 本地路径 映射")
    p.add_argument("--data-dir", default="data/raw", help="论文 JSON 所在目录")
    p.add_argument("--repos-dir", required=True, help="仓库根目录")
    p.add_argument("--output", default="data/repo_mapping.json", help="输出 JSON 路径")
    args = p.parse_args()
    papers = load_paper_data(args.data_dir)
    create_mapping(papers, args.repos_dir, args.output)


if __name__ == "__main__":
    main()
