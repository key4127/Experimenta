#!/usr/bin/env python3
"""
批量 clone GitHub（或 GitLab/Bitbucket）仓库。

输入：JSON 文件（含 code_url/repo_url/url 的列表）或纯文本（一行一个 URL）。
输出：每个仓库 clone 到 base_dir/owner_repo，已存在则跳过。

用法:
  python -m scripts.doc_agent.batch_clone_repos [--input FILE] [--out-dir DIR] [--token TOKEN] [--no-skip-existing]
  python -m scripts.doc_agent.batch_clone_repos --input data/test/iclr_papers_2025.json --out-dir ./repo

环境变量:
  GITHUB_TOKEN  可选，用于私有仓库（也可用 --token）
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# 项目根（仓库根目录，即 expreimenta/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def url_to_repo_name(repo_url: str, repo_type: str = "github") -> str:
    """从 URL 得到目录名，如 owner_repo。"""
    s = repo_url.strip().rstrip("/").replace("\\", "/")
    if s.endswith(".git"):
        s = s[:-4]
    parts = [p for p in s.split("/") if p]
    if repo_type in ("github", "gitlab", "bitbucket") and len(parts) >= 2:
        return f"{parts[-2]}_{parts[-1]}"
    return parts[-1] if parts else "repo"


def collect_urls_from_json(path: Path) -> list[str]:
    """从 JSON 里收集 code_url / repo_url / url，去重。"""
    seen: set[str] = set()
    urls: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("code_url") or item.get("repo_url") or item.get("url")
        if url and isinstance(url, str):
            u = url.strip()
            if u and u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def collect_urls_from_txt(path: Path) -> list[str]:
    """从纯文本收集 URL，一行一个，去重。"""
    seen: set[str] = set()
    urls: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip()
            if u and not u.startswith("#") and u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def is_auth_required_error(err: str) -> bool:
    """判断是否为需要鉴权/权限导致的错误（此类 repo 自动跳过）。"""
    err_lower = err.lower()
    auth_keywords = (
        "403",
        "401",
        "authentication failed",
        "permission denied",
        "could not read username",
        "support for password authentication was removed",
        "repository not found",
        "not found",
        "access denied",
        "unauthorized",
        "private repository",
        "authentication not supported",
    )
    return any(k in err_lower for k in auth_keywords)


def main() -> None:
    parser = argparse.ArgumentParser(description="批量 clone GitHub/GitLab/Bitbucket 仓库")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=PROJECT_ROOT / "data" / "test",
        help="输入：data/test 目录（默认）、或单个 JSON/.txt 文件",
    )
    parser.add_argument(
        "--out-dir", "-o",
        type=Path,
        default=None,
        help="clone 到的根目录，默认项目下的 repo/",
    )
    parser.add_argument(
        "--token", "-t",
        type=str,
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="Git 访问 token（私有仓库），默认用环境变量 GITHUB_TOKEN",
    )
    parser.add_argument(
        "--repo-type",
        choices=("github", "gitlab", "bitbucket"),
        default="github",
        help="仓库类型",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="已存在的目录也重新 clone（会先删再 clone）",
    )
    args = parser.parse_args()

    # 收集 URL
    inp = args.input
    if inp.is_dir():
        urls = []
        for p in sorted(inp.glob("*.json")):
            urls.extend(collect_urls_from_json(p))
        # 去重（多文件可能重复）
        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        urls = unique
    elif inp.suffix.lower() == ".json":
        urls = collect_urls_from_json(inp)
    else:
        urls = collect_urls_from_txt(inp)

    if not urls:
        print("未找到任何 URL。", file=sys.stderr)
        sys.exit(1)

    # 输出目录：默认当前项目下的 repo/
    if args.out_dir is not None:
        base_dir = Path(args.out_dir)
    else:
        base_dir = PROJECT_ROOT / "repo"
    base_dir = base_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    # 禁用内部 tqdm，压低日志，避免刷掉进度行
    tqdm_prev = os.environ.pop("TQDM_DISABLE", None)
    os.environ["TQDM_DISABLE"] = "1"
    root_logger = logging.getLogger()
    saved_level = root_logger.level
    for name in ("", "experimenta", "adalflow", "experimenta.agent", "experimenta.agent.deepwiki"):
        logging.getLogger(name).setLevel(logging.WARNING)

    try:
        from experimenta.agent.deepwiki.data_pipeline import download_repo
    except Exception as e:
        print(f"无法导入 download_repo: {e}", file=sys.stderr)
        sys.exit(1)

    total = len(urls)
    failed: list[tuple[str, str]] = []
    skipped_existing = 0
    skipped_auth: list[tuple[str, str]] = []

    for i, repo_url in enumerate(urls, 1):
        if i < 780:
            continue

        name = url_to_repo_name(repo_url, args.repo_type)
        local_path = base_dir / name
        sys.stdout.write(f"\rClone: {i}/{total}  {name} ...    ")
        sys.stdout.flush()

        # 已存在的 repo 自动跳过
        if local_path.exists() and any(local_path.iterdir()) and not args.no_skip_existing:
            skipped_existing += 1
            continue

        if args.no_skip_existing and local_path.exists():
            import shutil
            shutil.rmtree(local_path, ignore_errors=True)

        try:
            download_repo(
                repo_url,
                str(local_path),
                repo_type=args.repo_type,
                access_token=args.token or None,
            )
        except Exception as e:
            err_str = str(e)
            sys.stdout.write("\n")
            sys.stdout.flush()
            # 需要鉴权/权限的 repo 自动跳过，不视为失败
            if is_auth_required_error(err_str):
                print(f"跳过（需鉴权/无权限） {repo_url}: {err_str[:120]}", file=sys.stderr)
                skipped_auth.append((repo_url, err_str))
            else:
                print(f"失败 {repo_url}: {e}", file=sys.stderr)
                failed.append((repo_url, err_str))

    if tqdm_prev is not None:
        os.environ["TQDM_DISABLE"] = tqdm_prev
    else:
        os.environ.pop("TQDM_DISABLE", None)
    root_logger.setLevel(saved_level)

    success_count = total - len(failed) - len(skipped_auth) - skipped_existing
    print(f"\n完成。成功 {success_count}，跳过（已存在）{skipped_existing}，跳过（需鉴权）{len(skipped_auth)}，失败 {len(failed)} / {total}。")
    if skipped_auth:
        print("跳过（需鉴权）列表:", file=sys.stderr)
        for url, err in skipped_auth:
            print(f"  {url}: {err[:100]}", file=sys.stderr)
    if failed:
        print("失败列表:", file=sys.stderr)
        for url, err in failed:
            print(f"  {url}: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
