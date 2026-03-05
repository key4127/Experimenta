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

### Input Data Format
{
  "official_documents": "string containing authoritative technical content",
  "externel_snippets": ["array of strings representing existing research to exclude, optional"]
}

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


def synthesis_input(input, output):
    with open(input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    train_data = []

    for item in data:
        if item.get('web_response'):
            web_response = synthesis_web_response(item.get('web_response'))
            input = {
                "official_documents": item.get('docs'),
                "externel_snippets": synthesis_web_response(web_response)
            }
            input_str = json.dumps(input)
            train_data.append({
                "input": input_str,
                "instruction": INSTRUCTION,
                "output": item.get('abstract')
            })
        else:
            input = {
                "official_documents": item.get('docs')
            }
            input_str = json.dumps(input)
            train_data.append({
                "input": input_str,
                "instruction": INSTRUCTION,
                "output": item.get('abstract')
            })

    with open(output, 'w', encoding='utf-8') as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-input', type=Path)
    parser.add_argument('-output', type=Path)
    args = parser.parse_args()

    input = args.input.resolve()
    output = args.output.resolve()
    synthesis_input(input, output)