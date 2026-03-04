"""
为 data/test/sft.json 中每条数据根据 repo_url 从 GitHub API 获取仓库创建时间，
并添加 created_time 字段（格式 YYYY-MM-DD）。
需设置环境变量 GITHUB_TOKEN。
"""
import os
import re
import json
import argparse
from pathlib import Path
from datetime import datetime

import urllib.request
import urllib.error

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# 匹配 GitHub 仓库 URL，支持 .git 后缀和可选路径
GITHUB_REPO_PATTERN = re.compile(
    r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def parse_github_repo_url(url: str) -> tuple[str, str] | None:
    """从 GitHub URL 解析出 owner 和 repo 名。"""
    if not url or "github.com" not in url:
        return None
    m = GITHUB_REPO_PATTERN.match(url.strip())
    if not m:
        return None
    owner, repo = m.groups()
    return (owner, repo)


def get_repo_created_at(owner: str, repo: str) -> str | None:
    """
    通过 GitHub API 获取仓库创建时间，返回 YYYY-MM-DD 格式。
    使用环境变量 GITHUB_TOKEN 进行认证（可提高限流额度）。
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    req = urllib.request.Request(api_url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"token {GITHUB_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            created_at = data.get("created_at")
            if not created_at:
                return None
            # created_at 为 ISO 8601，如 2024-01-15T12:00:00Z
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, ValueError) as e:
        print(f"  [WARN] {owner}/{repo}: {e}")
        return None


def add_created_time_to_sft(sft_path: Path, *, in_place: bool = True, out_path: Path | None = None):
    """
    读取 sft.json，为每条数据根据 repo_url 获取仓库创建时间并添加 created_time 字段。
    :param sft_path: sft.json 文件路径
    :param in_place: 若为 True 则写回原文件；否则需指定 out_path
    :param out_path: 输出路径（in_place 为 False 时使用）
    """
    with open(sft_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("sft.json 应为 JSON 数组")

    total = len(data)
    for idx, item in enumerate(data):
        repo_url = item.get("repo_url") or ""
        if item.get("created_time"):
            continue  # 已有则跳过
        parsed = parse_github_repo_url(repo_url)
        if not parsed:
            item["created_time"] = ""
            if repo_url:
                print(f"  [WARN] 无法解析 URL: {repo_url}")
            continue
        owner, repo = parsed
        created = get_repo_created_at(owner, repo)
        item["created_time"] = created or ""
        if (idx + 1) % 20 == 0:
            print(f"  已处理 {idx + 1}/{total} 条")
        # 避免触发 GitHub 限流（未认证约 60/h）
        if not GITHUB_TOKEN and (idx + 1) % 50 == 0:
            import time
            time.sleep(60)

    write_path = sft_path if in_place else (out_path or sft_path.with_name("sft_with_created_time.json"))
    with open(write_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已写入 {write_path}，共 {total} 条")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="为 sft.json 每条数据添加 created_time（从 GitHub 仓库创建时间）")
    parser.add_argument(
        "-p", "--path",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "test" / "sft.json",
        help="sft.json 路径",
    )
    parser.add_argument("-o", "--output", type=Path, default=None, help="输出路径（不指定则原地覆盖）")
    args = parser.parse_args()
    path = args.path.resolve()
    if not path.exists():
        raise SystemExit(f"文件不存在: {path}")
    add_created_time_to_sft(path, in_place=args.output is None, out_path=args.output)
