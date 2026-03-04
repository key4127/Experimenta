import os
import json
import argparse
import random
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from tavily import TavilyClient


TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')

for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(key, None)

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


def websearch(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    n_total = len(data)
    n_sample = max(1, int(n_total * 0.75))
    indices = random.sample(range(n_total), n_sample)
    print(f'共 {n_total} 条，随机搜索 {n_sample} 条 (75%)')

    for progress, idx in enumerate(indices, start=1):
        item = data[idx]
        web = item.get('web_response')
        if web and web.get('answer'):
            continue
        try:
            raw = item.get('title') or ''
            query = f"Search for related papers: {raw}" if raw else ""
            created_time = item.get('created_time') or item.get('time')
            if created_time is None:
                end_date = None
            else:
                if isinstance(created_time, str):
                    created_dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                else:
                    created_dt = created_time
                end_date = (created_dt - relativedelta(months=1)).strftime('%Y-%m-%d')
            item['web_response'] = tavily_client.search(
                query=query,
                end_date=end_date,
                include_answer=True,
            )
        except Exception as e:
            print(f'跳过 idx={idx}: {e}')
            continue

        if progress % 20 == 0:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f'已写入 {progress} 条')

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='获取仓库文档的搜索信息')
    parser.add_argument('-p', type=Path)
    args = parser.parse_args()

    path = args.p.resolve()

    websearch(path)