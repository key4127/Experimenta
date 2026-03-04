import json
import argparse
from pathlib import Path


INSTRUCTION = """
### Role
You are an expert AI Research Scientist and Academic Architect.

### Task
Analyze the provided `official_documents` to identify a high-value, innovative research direction. Based on this direction, generate a formal scientific abstract.

### Constraints
1. **Primary Source**: Treat `official_documents` as the sole authoritative source for technical truth and unique implementation logic.
2. **Exclusion (External Results)**: Strictly avoid and bypass any research topics, methodologies, or findings mentioned in `externel_snippets`. These are "Negative References" representing existing or common research that must be excluded from your proposal.
3. **Innovation**: The proposed direction must represent a non-obvious, novel contribution that moves beyond existing trends found in external snippets.
4. **Output Format**: Return **ONLY** the text of the scientific abstract. Do not include titles, headers, introductory remarks, or any meta-explanation.

### Input Data
- **Official Documents**: {official_documents}
- **External Snippets (TO BE EXCLUDED)**: {externel_snippets}

### Output
[The abstract text only]
"""


def synthesis_web_response(web_response):
    webs = []
    for item in web_response:
        webs.append({
            "title": item.get('title'),
            "snippet": item.get('snippet')
        })
    return webs


def synthesis_input(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data:
        if item.get('web_response'):
            web_response = synthesis_web_response(item.get('web_response'))
            item['input'] = {
                "context": {
                    "official_documents": item.get('docs'),
                    "externel_snippets": synthesis_web_response(web_response)
                },
                "instruction": "",
                "response": item.get('abstract')
            }
        else:
            item['input'] = {
                "context": {
                    "official_documents": item.get('docs')
                },
                "instruction": """""",
                "response": item.get('abstract')
            }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', type=Path)
    args = parser.parse_args()

    path = args.p.resolve()
    synthesis_input(path)