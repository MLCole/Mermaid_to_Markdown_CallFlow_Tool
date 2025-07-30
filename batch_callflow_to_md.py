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


def extract_nodes_edges(mermaid_code):
    nodes = {}
    edges = []
    lines = mermaid_code.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        edge_match = re.match(r'(\S+)\s*--\|?(.*?)\|?-->\s*(\S+)', stripped)
        if edge_match:
            src, label, dst = edge_match.groups()
            edges.append((src.strip(), label.strip(), dst.strip()))
            continue
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
                break
    return nodes, edges


def build_graph(edges):
    graph = {}
    for src, _, dst in edges:
        graph.setdefault(src, []).append(dst)
    return graph


def resolve_final_label(nodes, graph, current, debug=False, trace=None, visited=None):
    if visited is None:
        visited = set()
    if current in visited:
        return None
    visited.add(current)
    label = nodes.get(current, '')

    if debug and trace is not None:
        trace.append(f"→ Looking at '{current}': {label}")

    match = re.search(r'\(\[(.*?)\]\)', label)
    if match:
        result = match.group(1).replace('<br>', ' ').strip()
        if debug and trace is not None:
            trace.append(f"✓ Found final bracketed label: {result}")
        return result

    if label and not re.match(r'^\+?1?\d{10,}$', label) and not re.fullmatch(r'[a-f0-9\-]{36}', label):
        if debug and trace is not None:
            trace.append(f"✓ Using fallback label: {label}")
        return label.strip()

    for next_node in graph.get(current, []):
        result = resolve_final_label(nodes, graph, next_node, debug, trace, visited)
        if result:
            return result

    if debug and trace is not None:
        trace.append("⚠ Reached dead end.")
    return None


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
    elif re.match(r"[a-z]+\\s+[a-z]+", label):
        return "🧑 Person"
    else:
        return "❓ Unknown"


def parse_auto_attendant(nodes, edges, debug=False):
    md = ["# 🤖 Auto Attendant Call Flow\n"]
    graph = build_graph(edges)

    if debug:
        print("🧠 NODE MAP:")
        for k, v in nodes.items():
            print(f"  {k}: {v}")
        print("\n➡ EDGES:")
        for src, lbl, dst in edges:
            print(f"  {src} --|{lbl}|--> {dst}")
        print("\n🔍 WALKING MENU PATHS:")

    incoming = [v for v in nodes.values() if "Incoming Call" in v]
    if incoming:
        md.append("## 📞 Entry Points")
        for i in incoming:
            md.append(f"- {i}")

    keypress_map = []
    for src, label, dst in edges:
        if label.strip().isdigit():
            trace = [f"🔑 Press `{label}` path:"]
            final_label = resolve_final_label(nodes, graph, dst, debug=debug, trace=trace)
            if final_label:
                keypress_map.append((label.strip(), final_label, categorize_target(final_label)))
            if debug:
                print("\n".join(trace) + "\n")

    if keypress_map:
        md.append("\n## 🔘 Main Menu Options")
        keypress_map.sort(key=lambda x: int(x[0]))
        for key, label, ttype in keypress_map:
            md.append(f"- Press `{key}` → {label} ({ttype})")

    return "\n".join(md)


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
                md.append(f"- **Yes** → {nodes.get(yes_edge[2], yes_edge[2])}")
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
            if re.match(r"[A-Za-z]+\\s+[A-Za-z]+", label) and "Voicemail" not in label:
                agent_section += f"\n  - {label}"
        md.append(agent_section)
    md.append("\n## 🔄 Agent Result Logic")
    if any("Agent Answered?" in v for v in nodes.values()):
        md.append("- If agent answers → Call connected")
        md.append("- If not answered → Timeout transfer to voicemail")
    if any("Agent Available?" in v for v in nodes.values()):
        md.append("- If no agent available → Transfer to voicemail")
    return "\n".join(md)


def write_markdown(md_text, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_text)
    print(f"✅ Saved: {output_file}")


def generate_markdown_from_html(html_file, debug=False):
    try:
        mermaid_code = extract_mermaid_code(html_file)
        nodes, edges = extract_nodes_edges(mermaid_code)
        if any("Menu" in v or "Press" in v or re.search(r'{Key Press', v) for v in nodes.values()):
            markdown = parse_auto_attendant(nodes, edges, debug=debug)
        elif any("Call Queue" in v or "Agent" in v for v in nodes.values()):
            markdown = parse_call_queue(nodes, edges)
        else:
            markdown = "# 🚧 Unsupported call flow format."
        output_path = Path(html_file).with_suffix(".md")
        write_markdown(markdown, output_path)
    except Exception as e:
        print(f"❌ Failed to process {html_file}: {e}")


def batch_process(folder_path, limit=None, debug=False):
    html_files = list(Path(folder_path).glob("*.htm")) + list(Path(folder_path).glob("*.html"))
    if limit:
        html_files = html_files[:limit]
    print(f"🔍 Found {len(html_files)} files to process in: {folder_path}")
    for file in html_files:
        generate_markdown_from_html(file, debug=debug)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch extract call flows from Mermaid HTML files into Markdown.")
    parser.add_argument("folder", help="Folder containing .htm/.html files")
    parser.add_argument("--limit", type=int, help="Number of files to process (optional)", default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    batch_process(args.folder, args.limit, debug=args.debug)
