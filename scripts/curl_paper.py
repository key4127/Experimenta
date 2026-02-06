import os
import json
from concurrent.futures import ThreadPoolExecutor

try:
    from openreview.api import OpenReviewClient
except ImportError:
    try:
        import openreview
        # 尝试使用旧版 API
        if hasattr(openreview, 'api'):
            OpenReviewClient = openreview.api.OpenReviewClient
        else:
            # 使用传统 Client
            OpenReviewClient = openreview.Client
    except ImportError:
        print("缺少依赖 openreview。请先安装：")
        print("  pip install openreview")
        print("或使用项目环境： uv sync 后在该环境中运行本脚本")
        raise SystemExit(1)

# 配置输出路径
output = './data/raw/'
if not os.path.exists(output):
    os.makedirs(output)

venue_id = 'NeurIPS.cc/2023/Conference'

def extract_paper_info(note):
    """提取论文信息"""
    try:
        paper_number = note.number
        title = note.content.get('title', {}).get('value', '')
        abstract = note.content.get('abstract', {}).get('value', '')
        
        return {
            'title': title,
            'id': paper_number,
            'abstract': abstract
        }
    except Exception as e:
        print(f"ID {note.number} 提取信息出错: {e}")
        return None

# 初始化主查询客户端
main_client = OpenReviewClient(baseurl='https://api2.openreview.net')

print(f"正在从 {venue_id} 获取论文列表...")
all_notes = main_client.get_all_notes(
    content={'venueid': venue_id}
)

# --- 核心修改部分：过滤标题 ---
# OpenReview V2 的 title 存储在 note.content['title']['value'] 中
accepted_notes = [
    note for note in all_notes 
    if 'vision' not in note.content['title']['value'].lower()
]
# ----------------------------

if not accepted_notes:
    print("未能获取到符合条件的论文。请确认过滤逻辑或 venue_id 是否准确。")
else:
    print(f"原始论文数: {len(all_notes)}")
    print(f"过滤后（排除标题含 'vision'）论文数: {len(accepted_notes)}")
    print("开始提取论文信息...")
    
    # 提取所有论文信息
    papers_data = []
    for note in accepted_notes:
        paper_info = extract_paper_info(note)
        if paper_info:
            print(f"已提取: {paper_info['id']} - {paper_info['title'][:30]}...")
            if 'https://github.com/' in paper_info.get('abstract'):
                abstract = paper_info.get('abstract')
                index = abstract.index('https://github.com/')
                url = abstract[index:]
                if url[-1] == '.':
                    url = url[:-1]
                paper_info['code_url'] = url
                papers_data.append(paper_info)

    # 保存为 JSON 文件
    output_file = os.path.join(output, 'neurips_papers_2023.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(papers_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n成功提取 {len(papers_data)} 篇论文信息")
    print(f"已保存到: {output_file}")

print("任务结束。")