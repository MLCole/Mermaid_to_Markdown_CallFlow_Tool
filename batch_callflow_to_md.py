import os
import re
from bs4 import BeautifulSoup
from pathlib import Path


def extract_mermaid_code(html_file):
    soup = BeautifulSoup(open(html_file, 'r', encoding='utf-8'), 'html.parser')
    code_block = soup.find('code', class_='language-mermaid')
    if not code_block:
        raise Exception(f"No Mermaid code block found in {html_file}")
    return code_block.text


def extract_nodes_edges(mermaid_code):
    nodes = {}
    edges = []
    lines = mermaid_code.splitlines()

    for line in lines:
        if '-->' in line or '-.->' in line or '---' in line:
            edges.append(line.strip())
        if '(((' in line or '((' in line or '[[' in line or '[(' in line:
            match = re.match(r'([a-zA-Z0-9_\-+]+)[ ]*\(\((.*?)\)\)', line)
            if match:
                nodes[match[1]] = match[2].replace('<br>', ' ').strip()
            continue
        match = re.match(r'([a-zA-Z0-9_\-+]+)\(\[(.*?)\]\)', line)
        if match:
            nodes[match[1]] = match[2].replace('<br>', ' ').strip()
            continue
        match = re.match(r'([a-zA-Z0-9_\-+]+)\[(.*?)\]', line)
        if match:
            nodes[match[1]] = match[2].replace('<br>', ' ').strip()
            continue
        match = re.match(r'([a-zA-Z0-9_\-+]+)\{(.*?)\}', line)
        if match:
            nodes[match[1]] = match[2].replace('<br>', ' ').strip()
            continue
    return nodes, edges


def parse_call_queue(nodes, edges):
    md = []
    name = next((label for label in nodes.values() if "Call Queue" in label), "Call Queue")

    md.append(f"# 📞 {name}\n")

    # Overflow
    for k, v in nodes.items():
        if "Active Calls?" in v:
            md.append(f"## 🔁 Overflow Condition\n- **Check**: {v}")
            yes_edge = next((e for e in edges if e.startswith(f"{k} --> |Yes|")), None)
            no_edge = next((e for e in edges if e.startswith(f"{k} ---> |No|")), None)
            if yes_edge:
                md.append(f"- **Yes** → {get_target_label(yes_edge, nodes)}")
            if no_edge:
                md.append(f"- **No** → Routing continues")
            break

    # Routing Method
    routing = [v for v in nodes.values() if "Routing Method" in v]
    if routing:
        md.append(f"\n## 🧭 Routing Method\n- {routing[0]}")

    # Timeout
    timeouts = [v for v in nodes.values() if "Timeout" in v]
    if timeouts:
        md.append(f"\n## ⏱ Timeout\n- {timeouts[0]}")

    # Settings
    settings = [v for v in nodes.values() if "Music On Hold" in v]
    if settings:
        md.append(f"\n## ⚙️ Queue Settings\n- {settings[0]}")

    # Agents
    agent_section = "\n## 👥 Agent List"
    agent_list = [v for v in nodes.values() if "Agent List Type" in v]
    if agent_list:
        agent_section += f"\n- {agent_list[0]}"
        for label in nodes.values():
            if re.match(r"[A-Za-z]+\s+[A-Za-z]+", label) and "Voicemail" not in label:
                agent_section += f"\n  - {label}"
        md.append(agent_section)

    # Result logic
    md.append("\n## 🔄 Agent Result Logic")
    if any("Agent Answered?" in v for v in nodes.values()):
        md.append("- If agent answers → Call connected")
        md.append("- If not answered → Timeout transfer to voicemail")

    if any("Agent Available?" in v for v in nodes.values()):
        md.append("- If no agent available → Transfer to voicemail")

    return "\n".join(md)


def get_target_label(edge, nodes):
    parts = re.split(r'-->|--->|-.->|--\|.*?\|', edge)
    if len(parts) >= 2:
        target = parts[-1].strip()
        target = re.sub(r'\((.*?)\)', '', target).strip()
        return nodes.get(target, target)
    return "Unknown"


def write_markdown(md_text, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_text)
    print(f"✅ Saved: {output_file}")


def generate_markdown_from_html(html_file):
    try:
        mermaid_code = extract_mermaid_code(html_file)
        nodes, edges = extract_nodes_edges(mermaid_code)

        if any("Call Queue" in v for v in nodes.values()):
            markdown = parse_call_queue(nodes, edges)
        else:
            markdown = "# 🚧 Unsupported or non-queue structure."

        output_path = Path(html_file).with_suffix(".md")
        write_markdown(markdown, output_path)

    except Exception as e:
        print(f"❌ Failed to process {html_file}: {e}")


def batch_process(folder_path, limit=None):
    html_files = list(Path(folder_path).glob("*.htm")) + list(Path(folder_path).glob("*.html"))

    if limit:
        html_files = html_files[:limit]

    print(f"🔍 Found {len(html_files)} files to process in: {folder_path}")
    for file in html_files:
        generate_markdown_from_html(file)


# ---------- MAIN EXECUTION ----------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch extract call flows from Mermaid HTML files into Markdown.")
    parser.add_argument("folder", help="Folder containing .htm/.html files")
    parser.add_argument("--limit", type=int, help="Number of files to process (optional)", default=None)
    args = parser.parse_args()

    batch_process(args.folder, args.limit)
