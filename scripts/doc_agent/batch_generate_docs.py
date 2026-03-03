"""
遍历指定目录下的 JSON 文件，对其中每个 code_url 调用 experimenta/agent/deepwiki
生成「概括仓库内容」并保存为 JSON。

用法:
  python -m scripts.doc_agent.batch_generate_docs [--input DIR] [--repo-dir DIR] [--output DIR] [--provider NAME] [--language LANG]
  python -m scripts.doc_agent.batch_generate_docs --input data/test --output ./out
"""

# 440

import argparse
import asyncio
import logging
import os
import json
import re
import sys
from pathlib import Path

# 暂时取消所有代理，避免请求走代理
for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(key, None)

from experimenta.agent.deepwiki.chat import (
    chat_completions_stream,
    ChatCompletionRequest,
    ChatMessage,
)

# 项目根目录（仓库根）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 概括仓库的提示词：要求完整、规范、细粒度的项目文档（英文）
SUMMARY_PROMPT = """Generate a complete, standardized project documentation for this repository. Requirements:

**Completeness & granularity**
- Cover every major component, module, package, and script. Do not summarize at a high level only; go into sufficient detail so that each piece of work in the repo is clearly described.
- For each component: state its purpose, inputs/outputs, key functions or classes, and how it connects to other parts. Reference specific file paths and symbols (e.g. `src/foo/bar.py::Baz.qux`) where relevant.
- Include: entry points and CLI usage, configuration options and environment variables, data formats and schemas, external dependencies and APIs, and any notable algorithms or formulas.

**Structure (use these sections in markdown)**
- **Overview**: project goal, scope, and main deliverables.
- **Architecture**: directory layout, module dependency graph, and design patterns.
- **Components**: per-package or per-module description with responsibilities and key interfaces.
- **Workflows**: end-to-end flows (e.g. training, inference, serving), with steps and which code implements them.
- **Configuration & environment**: all config files, env vars, and defaults, with meaning and where they are used.
- **Data & I/O**: input/output formats, paths, and any schema or preprocessing.
- **Dependencies**: runtime and dev dependencies, versions if critical, and how they are used.
- **Limitations & assumptions**: what the code assumes (hardware, data, external services) and known limitations.

**Style**
- Write in clear, formal English. Use consistent terminology and cross-references.
- Be specific: prefer “function X in file Y does Z” over vague descriptions. The documentation should allow someone to understand and trace every significant part of the repository."""


def load_repo_entries_from_test_data(data_dir: Path) -> list[tuple[str, dict]]:
    """
    遍历指定目录下所有 .json，收集带 code_url 的条目。
    返回 [(code_url, meta), ...]，meta 为原条目中 title、id 等（用于写入结果）。
    同一 URL 只保留第一次出现的条目。
    """
    seen_urls: set[str] = set()
    entries: list[tuple[str, dict]] = []
    if not data_dir.is_dir():
        return entries
    for path in sorted(data_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  跳过 {path}: 读取失败 {e}")
            continue
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get("code_url") or item.get("repo_url") or item.get("url")
            if not url or not isinstance(url, str) or url.strip() in seen_urls:
                continue
            seen_urls.add(url.strip())
            meta = {k: v for k, v in item.items() if k != "code_url" and k in ("title", "id", "abstract")}
            entries.append((url.strip(), meta))
    return entries


def url_to_repo_name(repo_url: str, repo_type: str = "github") -> str:
    """从 URL 得到与 batch_clone_repos 一致的目录名，如 owner_repo。"""
    s = repo_url.strip().rstrip("/").replace("\\", "/")
    if s.endswith(".git"):
        s = s[:-4]
    parts = [p for p in s.split("/") if p]
    if repo_type in ("github", "gitlab", "bitbucket") and len(parts) >= 2:
        return f"{parts[-2]}_{parts[-1]}"
    return parts[-1] if parts else "repo"


def url_to_safe_filename(repo_url: str) -> str:
    """将仓库 URL 转为安全的 JSON 文件名（不含路径分隔符）。"""
    s = repo_url.strip().rstrip("/")
    # 去掉 .git 后缀
    if s.endswith(".git"):
        s = s[:-4]
    # 取最后两段：owner/repo -> owner_repo
    parts = [p for p in s.replace("\\", "/").split("/") if p]
    if len(parts) >= 2:
        name = "_".join(parts[-2:])
    else:
        name = parts[-1] if parts else "repo"
    # 只保留安全字符
    name = re.sub(r"[^\w\-.]", "_", name)
    return f"{name}.json"


def resolve_repo_path(repo_url: str, repo_dir: Path, repo_type: str = "github") -> str | None:
    """
    若 repo_dir 下已有该仓库的 clone（与 batch_clone_repos 同规则），返回本地路径；
    否则返回 None（调用方应跳过该仓库）。
    """
    local_name = url_to_repo_name(repo_url, repo_type)
    local_path = repo_dir / local_name
    if local_path.is_dir() and any(local_path.iterdir()):
        return str(local_path.resolve())
    return None


async def get_repo_summary(
    repo_path_or_url: str,
    provider: str,
    language: str,
) -> str:
    """调用 deepwiki 对单个仓库生成概括，返回完整回复文本。repo_path_or_url 为本地路径或 URL。"""
    request = ChatCompletionRequest(
        repo_url=repo_path_or_url,
        messages=[ChatMessage(role="user", content=SUMMARY_PROMPT)],
        provider=provider,
        language=language,
    )
    response = await chat_completions_stream(request)
    chunks = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8", errors="replace")
        chunks.append(chunk)
    return "".join(chunks).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量对仓库生成概括文档（deepwiki）")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=PROJECT_ROOT / "data" / "test",
        help="输入目录：包含 code_url 的 JSON 文件所在目录，默认 data/test",
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=PROJECT_ROOT / "repo",
        help="本地仓库根目录（与 batch_clone_repos 一致），默认 repo/",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=PROJECT_ROOT / "tmp" / "generate_docs",
        help="输出目录，默认 tmp/generate_docs",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="deepseek",
        help="模型 provider，默认 deepseek",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="文档语言，默认 en",
    )
    parser.add_argument(
        "--repo-type",
        choices=("github", "gitlab", "bitbucket"),
        default="github",
        help="仓库类型（用于解析本地路径名）",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    data_dir = args.input.resolve()
    repo_dir = args.repo_dir.resolve()
    output_dir = args.output.resolve()

    entries = load_repo_entries_from_test_data(data_dir)
    if not entries:
        print(f"在 {data_dir} 下未找到包含 code_url 的 JSON 条目。")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # 压低其它日志，避免刷屏
    root = logging.getLogger()
    saved = root.level
    for name in ("", "experimenta", "adalflow", "experimenta.agent", "experimenta.agent.deepwiki"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # 禁用内部 tqdm（adalflow 的 splitting/embedding 等），否则会盖掉本脚本的进度
    tqdm_disabled = os.environ.pop("TQDM_DISABLE", None)
    os.environ["TQDM_DISABLE"] = "1"

    total = len(entries)
    try:
        for i, (repo_url, meta) in enumerate(entries, 1):
            # if i < 91:
            #     continue
            repo_short = repo_url.rstrip("/").split("/")[-1].replace(".git", "")[:24]
            sys.stdout.write(f"\rRepos: {i}/{total}  {repo_short} ...    ")
            sys.stdout.flush()
            try:
                repo_path_or_url = resolve_repo_path(repo_url, repo_dir, args.repo_type)
                if repo_path_or_url is None:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    print(f"跳过（本地无 clone）: {repo_url}", file=sys.stderr)
                    continue
                # 若已存在非 error 的输出文件则跳过，不再调用 API
                out_path = output_dir / url_to_safe_filename(repo_url)
                if out_path.is_file():
                    continue
                summary = await get_repo_summary(
                    repo_path_or_url, args.provider, args.language
                )
                out = {
                    "repo_url": repo_url,
                    "docs": summary,
                    **meta,
                }
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
            except Exception as e:
                sys.stdout.write("\n")
                sys.stdout.flush()
                print(f"失败 {repo_url}: {e}", file=sys.stderr)
                err_path = output_dir / (url_to_safe_filename(repo_url).replace(".json", "_error.json"))
                with open(err_path, "w", encoding="utf-8") as f:
                    json.dump({"repo_url": repo_url, "error": str(e), **meta}, f, ensure_ascii=False, indent=2)
    finally:
        if tqdm_disabled is not None:
            os.environ["TQDM_DISABLE"] = tqdm_disabled
        else:
            os.environ.pop("TQDM_DISABLE", None)
        logging.getLogger().setLevel(saved)

    print("\n全部完成。")


if __name__ == "__main__":
    asyncio.run(main())
