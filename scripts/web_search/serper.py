import os
import json
import time
import argparse
import random
import http.client
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta


SERPER_API_KEY = os.environ.get("SERPER_DEV_API_KEY")

for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(key, None)


def serper_search(query: str, end_date: str | None = None) -> dict:
    """
    使用 Serper API 进行网页搜索。
    end_date: 若提供 (YYYY-MM-DD)，则仅在 end_date 之前的结果中搜索（通过 query 中加 before:YYYY/MM/DD）。
    """
    conn = http.client.HTTPSConnection("google.serper.dev")
    q = query
    if end_date:
        # Google 操作符 before: 使用 YYYY/MM/DD
        before_str = end_date.replace("-", "/")
        q = f"{query} before:{before_str}"
    payload = json.dumps({"q": q})
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    start_time = time.perf_counter()
    conn.request("POST", "/search", payload, headers)
    res = conn.getresponse()
    data = res.read()
    conn.close()
    print(f"search time: {time.perf_counter() - start_time:.2f}s")
    out = json.loads(data.decode())
    # 兼容下游对 answer 的检查：从 answerBox 或 knowledgeGraph 取摘要
    if "answer" not in out and isinstance(out.get("answerBox"), dict):
        out["answer"] = out["answerBox"].get("answer") or out["answerBox"].get("snippet")
    elif "answer" not in out and isinstance(out.get("knowledgeGraph"), dict):
        out["answer"] = out["knowledgeGraph"].get("description")
    return out


def _is_serper_error(out: dict) -> bool:
    """API 返回错误（如额度不足）时返回 True，不写入、不视为已有 serper。"""
    if not out or not isinstance(out, dict):
        return True
    if "statusCode" in out:
        return True
    if out.get("message") == "Not enough credits":
        return True
    return False


def _has_serper_response(item: dict) -> bool:
    """
    已有 serper 结果时返回 True，tavily result 不计入。
    若 web_response 是 API 错误（statusCode / Not enough credits）则不视为已有，便于额度恢复后重跑。
    无 web_response_source 时按响应结构推断：Serper 有 organic，Tavily 有 response_time。
    """
    web = item.get("web_response")
    if not web or not isinstance(web, dict):
        return False
    # API 错误响应不计入，下次可重试
    if _is_serper_error(web):
        return False
    # 明确标记优先
    if item.get("web_response_source") == "tavily":
        return False
    if item.get("web_response_source") == "serper":
        return True
    # Tavily 返回带 response_time
    if "response_time" in web:
        return False
    # Serper 返回带 organic（搜索结果列表），旧数据无 source 时据此推断
    return "organic" in web


def websearch(path: Path) -> None:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    n_total = len(data)
    # 已有 serper 的实例（tavily result 不计入）
    has_serper_indices = {i for i in range(n_total) if _has_serper_response(data[i])}
    n_has_serper = len(has_serper_indices)
    # 目标：总体的 75% 需要 serper 搜索
    need_count = max(1, int(n_total * 0.75))
    to_fill = max(0, need_count - n_has_serper)
    # 在尚未有 serper 的实例中抽取
    remaining = [i for i in range(n_total) if i not in has_serper_indices]
    n_sample = min(to_fill, len(remaining))
    indices = random.sample(remaining, n_sample) if n_sample else []
    print(
        f"共 {n_total} 条，已有 serper {n_has_serper} 条，目标 75%={need_count} 条，"
        f"本次在剩余 {len(remaining)} 条中抽取 {n_sample} 条"
    )

    for progress, idx in enumerate(indices, start=1):
        item = data[idx]
        if _has_serper_response(item):
            continue
        try:
            raw = item.get("title") or ""
            query = f"Search for related papers: {raw}" if raw else ""
            created_time = item.get("created_time") or item.get("time")
            if created_time is None:
                end_date = None
            else:
                if isinstance(created_time, str):
                    created_dt = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                else:
                    created_dt = created_time
                end_date = (created_dt - relativedelta(months=1)).strftime("%Y-%m-%d")
            raw = serper_search(query, end_date)
            if _is_serper_error(raw):
                print(f"跳过 idx={idx}: API 错误 {raw.get('message', raw.get('statusCode', raw))}，不写入，额度恢复后可重跑")
                # 清除该条已有的错误响应，保证错误不计入 json
                item.pop("web_response", None)
                item.pop("web_response_source", None)
                continue
            item["web_response"] = raw
            item["web_response_source"] = "serper"
        except Exception as e:
            print(f"跳过 idx={idx}: {e}")
            continue

        if progress % 20 == 0:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"已写入 {progress} 条")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="获取仓库文档的搜索信息 (Serper)")
    parser.add_argument("-p", type=Path)
    args = parser.parse_args()

    path = args.p.resolve()
    websearch(path)
