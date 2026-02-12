"""
遍历 data/test 下的 JSON 文件，对其中每个 code_url 调用 experimenta/agent/deepwiki
生成「概括仓库内容」并保存为 JSON。
"""
import asyncio
import json
import re
from pathlib import Path

from experimenta.agent.deepwiki.chat import (
    chat_completions_stream,
    ChatCompletionRequest,
    ChatMessage,
)

# 项目根目录（仓库根）与 data/test 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_TEST_DIR = PROJECT_ROOT / "data" / "test"

# 输出目录（相对本脚本所在目录）
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# 使用的模型与语言（不再使用 Google，改为 DeepSeek）
PROVIDER = "deepseek"
LANGUAGE = "zh"

# 概括仓库的提示词
SUMMARY_PROMPT = "请根据仓库内容，详细生成仓库相关的完整文档。"


def load_repo_entries_from_test_data() -> list[tuple[str, dict]]:
    """
    遍历 data/test 下所有 .json，收集带 code_url 的条目。
    返回 [(code_url, meta), ...]，meta 为原条目中 title、id 等（用于写入结果）。
    同一 URL 只保留第一次出现的条目。
    """
    seen_urls: set[str] = set()
    entries: list[tuple[str, dict]] = []
    if not DATA_TEST_DIR.is_dir():
        return entries
    for path in sorted(DATA_TEST_DIR.glob("*.json")):
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


async def get_repo_summary(repo_url: str) -> str:
    """调用 deepwiki 对单个仓库生成概括，返回完整回复文本。"""
    request = ChatCompletionRequest(
        repo_url=repo_url,
        messages=[ChatMessage(role="user", content=SUMMARY_PROMPT)],
        provider=PROVIDER,
        language=LANGUAGE,
    )
    response = await chat_completions_stream(request)
    chunks = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8", errors="replace")
        chunks.append(chunk)
    return "".join(chunks).strip()


async def main():
    entries = load_repo_entries_from_test_data()
    if not entries:
        print(f"在 {DATA_TEST_DIR} 下未找到包含 code_url 的 JSON 条目。")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = len(entries)

    for i, (repo_url, meta) in enumerate(entries, 1):
        print(f"[{i}/{total}] 正在处理: {repo_url}")
        try:
            summary = await get_repo_summary(repo_url)
            out = {
                "repo_url": repo_url,
                "概括仓库内容": summary,
                **meta,
            }
            filename = url_to_safe_filename(repo_url)
            out_path = OUTPUT_DIR / filename
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"    已保存: {out_path}")
        except Exception as e:
            print(f"    失败: {e}")
            err_path = OUTPUT_DIR / (url_to_safe_filename(repo_url).replace(".json", "_error.json"))
            with open(err_path, "w", encoding="utf-8") as f:
                json.dump({"repo_url": repo_url, "error": str(e), **meta}, f, ensure_ascii=False, indent=2)

    print("全部完成。")


if __name__ == "__main__":
    asyncio.run(main())
