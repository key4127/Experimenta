import json
from pathlib import Path


input_dir = './data/raw'
output = './data/merge/merge.json'

base_path = Path(input_dir)

data = []

for path in base_path.rglob('*'):
    with open(path, 'r', encoding='utf-8') as f:
        cur_data = json.load(f)
    data.extend(cur_data)

with open(output, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)