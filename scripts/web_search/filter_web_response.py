import json
import argparse
from pathlib import Path


def filter_web_response(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data:
        if item.get('web_response') and item.get('web_response').get('organic'):
            web_result = item.get('web_response').get('organic')
        else:
            web_result = []
        item['web_response'] = web_result

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', type=Path)
    args = parser.parse_args()

    path = args.p.resolve()
    filter_web_response(path)
