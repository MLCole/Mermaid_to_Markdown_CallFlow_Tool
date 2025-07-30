import os
import re
import logging
from bs4 import BeautifulSoup
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def extract_mermaid_code(html_file):
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    code_block = soup.find('code', class_='language-mermaid')
    if not code_block:
        raise Exception(f"No Mermaid code block found in {html_file}")
    return code_block.text

def extract_nodes_edges(mermaid_code, filename=None):
    nodes = {}
    edges = []
    unmatched_lines = []
    lines = mermaid_code.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        matched = False
        if any(op in stripped for op in ['-->', '-.->', '---']):
            edge_match = re.match(r'(\S+)\s*--\|?(.*?)\|?-->\s*(\S+)', stripped)
            if edge_match:
                src, label, dst = edge_match.groups()
                edges.append((src.strip(), label.strip(), dst.strip()))
                matched = True
        node_patterns = [
            r'([a-zA-Z0-9_\-]+)\s*\(\((.*?)\)\)',
            r'([a-zA-Z0-9_\-]+)\(\[(.*?)\]\)',
            r'([a-zA-Z0-9_\-]+)\[(.*?)\]',
            r'([a-zA-Z0-9_\-]+)\{(.*?)\}',
            r'([a-zA-Z0-9_\-]+)>\s*(.*?)\]',
            r'(user[a-zA-Z]+[a-zA-Z0-9_\-]*)\((.*?)\)',
        ]
        for pattern in node_patterns:
            match = re.search(pattern, stripped)
            if match:
                label_text = match.group(2).replace('<br>', ' ').strip()
                nodes[match.group(1)] = label_text
                matched = True
                break
        if not matched and re.fullmatch(r'[0-9a-fA-F\-]{36}', stripped):
            nodes[stripped] = stripped
            matched = True
        if not matched:
            unmatched_lines.append(stripped)
    if unmatched_lines:
        file_label = f"[{filename}]" if filename else ""
        logging.warning(f"{file_label} Unmatched Mermaid lines:")
        for ul in unmatched_lines:
            logging.warning(f"  >> {ul}")
    return nodes, edges

def parse_auto_attendant(nodes, edges):
    md = ["# 🤖 Auto Attendant Call Flow\n"]

    incoming = [v for v in nodes.values() if "Incoming Call" in v]
    if incoming:
        md.append("## 📞 Entry Points")
        for i in incoming:
            md.append(f"- {i}")

    # Map all menu transitions that contain a keypress number as the label (e.g. '|1|')
    keypress_map = []
    for src, label, dst in edges:
        if label.strip().isdigit():
            option = label.strip()
            final_target = resolve_final_target(dst, edges, nodes)
            target_label = nodes.get(final_target, final_target)
            target_type = categorize_target(target_label)
            keypress_map.append((option, target_label, target_type))

    if keypress_map:
        md.append("\n## 🔘 Main Menu Options")
        try:
            keypress_map.sort(key=lambda x: int(x[0]))
        except:
            keypress_map.sort(key=lambda x: x[0])
        for key, label, ttype in keypress_map:
            md.append(f"- Press `{key}` → {label} ({ttype})")

    return "\n".join(md)

def resolve_final_target(start_id, edges, nodes, depth=0, visited=None):
    if visited is None:
        visited = set()
    if start_id in visited or depth > 10:
        return start_id
    visited.add(start_id)
    next_hops = [dst for src, lbl, dst in edges if src == start_id and not lbl.strip().isdigit()]
    if not next_hops:
        return start_id
    return resolve_final_target(next_hops[0], edges, nodes, depth + 1, visited)

def categorize_target(label):
    label = label.lower()
    if "voicemail" in label:
        return "📩 Voicemail"
    elif "greeting" in label or "transfer message" in label:
        return "📩 Greeting"
    elif "directory" in label:
        return "🔂 Directory"
    elif "queue" in label:
        return "🔁 Call Queue"
    elif "transfer" in label or "external" in label or "forward" in label:
        return "📞 External Transfer"
    elif re.match(r"[a-z]+\s+[a-z]+", label):
        return "🧑 Person"
    else:
        return "❓ Unknown"

def parse_call_queue(nodes, edges):
    md = []
    name = next((label for label in nodes.values() if "Call Queue" in label), "Call Queue")
    md.append(f"# 📞 {name}\n")
    for k, v in nodes.items():
        if "Active Calls?" in v:
            md.append(f"## 🔁 Overflow Condition\n- **Check**: {v}")
            yes_edge = next(((s, l, d) for (s, l, d) in edges if s == k and l.lower() == "yes"), None)
            no_edge = next(((s, l, d) for (s, l, d) in edges if s == k and l.lower() == "no"), None)
            if yes_edge:
                md.append(f"- **Yes** → {get_target_label(yes_edge[2], nodes)}")
            if no_edge:
                md.append(f"- **No** → Routing continues")
            break

    routing = [v for v in nodes.values() if "Routing Method" in v]
    if routing:
        md.append(f"\n## 🧽 Routing Method\n- {routing[0]}")
    timeouts = [v for v in nodes.values() if "Timeout" in v]
    if timeouts:
        md.append(f"\n## ⏱ Timeout\n- {timeouts[0]}")
    settings = [v for v in nodes.values() if "Music On Hold" in v]
    if settings:
        md.append(f"\n## ⚙️ Queue Settings\n- {settings[0]}")
    agent_section = "\n## 👥 Agent List"
    agent_list = [v for v in nodes.values() if "Agent List Type" in v]
    if agent_list:
        agent_section += f"\n- {agent_list[0]}"
        for label in nodes.values():
            if re.match(r"[A-Za-z]+\s+[A-Za-z]+", label) and "Voicemail" not in label:
                agent_section += f"\n  - {label}"
        md.append(agent_section)
    md.append("\n## 🔄 Agent Result Logic")
    if any("Agent Answered?" in v for v in nodes.values()):
        md.append("- If agent answers → Call connected")
        md.append("- If not answered → Timeout transfer to voicemail")
    if any("Agent Available?" in v for v in nodes.values()):
        md.append("- If no agent available → Transfer to voicemail")
    return "\n".join(md)

def get_target_label(target, nodes):
    return nodes.get(target, target)

def write_markdown(md_text, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_text)
    print(f"✅ Saved: {output_file}")

def generate_markdown_from_html(html_file):
    try:
        mermaid_code = extract_mermaid_code(html_file)
        nodes, edges = extract_nodes_edges(mermaid_code, html_file)
        if any("Menu" in v or "Press" in v or re.search(r'{Key Press', v) for v in nodes.values()):
            markdown = parse_auto_attendant(nodes, edges)
        elif any("Call Queue" in v or "Agent" in v for v in nodes.values()):
            markdown = parse_call_queue(nodes, edges)
        else:
            markdown = "# 🚧 Unsupported call flow format."
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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch extract call flows from Mermaid HTML files into Markdown.")
    parser.add_argument("folder", help="Folder containing .htm/.html files")
    parser.add_argument("--limit", type=int, help="Number of files to process (optional)", default=None)
    args = parser.parse_args()
    batch_process(args.folder, args.limit)
