"""
将 data/test/all.json 按比例拆分为 test.json、sft.json、dpo.json。

- test.json: 随机 10%
- sft.json: 80%
- dpo.json: 一半来自「除 test、sft 外的剩余 10%」，一半来自「sft 中的 10%」（两半等量）

用法:
  python -m scripts.tavily.split_all_to_dpo_sft_test [--input FILE] [--out-dir DIR] [--seed N]
"""
import argparse
import json
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 all.json 拆分为 test / sft / dpo")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=PROJECT_ROOT / "data" / "test" / "all.json",
        help="输入的 all.json 路径",
    )
    parser.add_argument(
        "--out-dir", "-o",
        type=Path,
        default=PROJECT_ROOT / "data" / "test",
        help="输出目录，将写入 test.json / sft.json / dpo.json",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子，默认 42",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input.resolve()
    out_dir = args.out_dir.resolve()

    if not input_path.is_file():
        print(f"输入文件不存在: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("输入应为 JSON 数组")
        return

    random.seed(args.seed)
    N = len(data)
    indices = list(range(N))
    random.shuffle(indices)

    n_test = max(1, int(round(0.10 * N)))
    n_sft = max(1, int(round(0.80 * N)))
    # 先取 10% 为 test，再从剩余中取 80% 为 sft，剩下 10% 为 remaining
    i_test = indices[:n_test]
    rest_indices = indices[n_test:]
    i_sft = rest_indices[:n_sft]
    i_remaining = rest_indices[n_sft:]  # 约 10% 总量

    # dpo: 全部 remaining + 从 sft 中抽约 10%（与 remaining 等量，不要求严格一致）；多出来的都进 dpo
    n_from_sft = min(len(i_remaining), max(1, int(round(0.10 * len(i_sft)))))
    dpo_from_remaining = list(i_remaining)  # 全部写入 dpo，无未写入
    dpo_from_sft = random.sample(i_sft, n_from_sft)
    i_dpo = dpo_from_remaining + dpo_from_sft
    random.shuffle(i_dpo)

    test_data = [data[i] for i in i_test]
    sft_data = [data[i] for i in i_sft]
    dpo_data = [data[i] for i in i_dpo]

    out_dir.mkdir(parents=True, exist_ok=True)

    for name, arr in [("test.json", test_data), ("sft.json", sft_data), ("dpo.json", dpo_data)]:
        out_path = out_dir / name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(arr, f, ensure_ascii=False, indent=2)
        print(f"已写 {name}: {len(arr)} 条 -> {out_path}")


if __name__ == "__main__":
    main()
