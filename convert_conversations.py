"""Convert a claude.ai data export into one Markdown transcript per conversation.

Usage: python -I convert_conversations.py <export_dir> <out_dir>

Writes <out_dir>/<project>/<date>_<title>.md and <out_dir>/manifest.json.
Only the active branch of each conversation is kept (the path ending at the
most recent message). Thinking blocks are dropped; tool calls are summarized,
except files Claude created, which are kept in full.
"""
import glob
import json
import os
import re
import sys

ROOT_PARENT = "00000000-0000-4000-8000-000000000000"
TOOL_INPUT_LIMIT = 400
TOOL_RESULT_LIMIT = 300


def safe_name(s, limit=80):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s or "").strip().rstrip(".")
    return (s[:limit].strip() or "untitled")


def clip(s, n):
    s = s.strip()
    return s if len(s) <= n else s[:n] + f" … [{len(s) - n} more chars]"


def active_branch(messages):
    by_id = {m["uuid"]: m for m in messages}
    if not messages:
        return []
    cur = max(messages, key=lambda m: m["created_at"])
    path = []
    while cur is not None:
        path.append(cur)
        cur = by_id.get(cur["parent_message_uuid"])
    return list(reversed(path))


def result_text(content):
    if isinstance(content, str):
        return content
    parts = []
    for c in content or []:
        if isinstance(c, dict):
            parts.append(c.get("text") or json.dumps(c, ensure_ascii=False))
        else:
            parts.append(str(c))
    return "\n".join(parts)


def render_block(b):
    t = b.get("type")
    if t == "text":
        return (b.get("text") or "").strip()
    if t == "tool_use":
        name, inp = b.get("name"), b.get("input") or {}
        if name == "create_file" and isinstance(inp, dict):
            path = inp.get("path", "")
            body = inp.get("file_text") or inp.get("content") or ""
            return f"> 📄 **Created file `{path}`**\n\n````\n{body}\n````"
        return f"> 🔧 **Tool `{name}`**: `{clip(json.dumps(inp, ensure_ascii=False), TOOL_INPUT_LIMIT)}`"
    if t == "tool_result":
        txt = clip(result_text(b.get("content")), TOOL_RESULT_LIMIT).replace("\n", " ")
        flag = " (error)" if b.get("is_error") else ""
        return f"> ↳ result{flag}: {txt}" if txt else ""
    return ""  # thinking, injected prompts, token budgets


def render_message(m):
    who = "You" if m["sender"] == "human" else "Claude"
    blocks = [render_block(b) for b in m.get("content") or []]
    body = "\n\n".join(x for x in blocks if x)
    if not body:
        body = (m.get("text") or "").strip()
    for f in m.get("files") or []:
        body += f"\n\n_(attached file: {f.get('file_name', '?')})_"
    return f"### {who} — {m['created_at'][:16].replace('T', ' ')} UTC\n\n{body}\n"


def main(export_dir, out_dir):
    convos = json.load(open(os.path.join(export_dir, "conversations-000", "conversations.json"), encoding="utf-8"))
    projects = {}
    for f in glob.glob(os.path.join(export_dir, "projects-000", "projects", "*.json")):
        p = json.load(open(f, encoding="utf-8"))
        projects[p["uuid"]] = p["name"]

    manifest = []
    for c in sorted(convos, key=lambda c: c["created_at"]):
        msgs = active_branch(c.get("chat_messages") or [])
        if not msgs:
            continue
        proj = projects.get(c.get("project_uuid") or "", None)
        folder = os.path.join(out_dir, safe_name(proj) if proj else "_no_project")
        os.makedirs(folder, exist_ok=True)
        title = c.get("name") or "Untitled"
        fname = f"{c['created_at'][:10]}_{safe_name(title, 60)}.md"
        path = os.path.join(folder, fname)

        header = [
            f"# {title}",
            "",
            f"- Original conversation: {c['uuid']}",
            f"- Project: {proj or '(none)'}",
            f"- Started: {c['created_at'][:16].replace('T', ' ')} UTC · Last updated: {c['updated_at'][:16].replace('T', ' ')} UTC",
            f"- Messages (active branch): {len(msgs)}",
            "",
        ]
        if c.get("summary"):
            header += ["## Summary", "", c["summary"].strip(), ""]
        header += ["## Transcript", ""]
        text = "\n".join(header) + "\n".join(render_message(m) for m in msgs)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

        manifest.append({
            "uuid": c["uuid"],
            "title": title,
            "project_uuid": c.get("project_uuid"),
            "project_name": proj,
            "file": os.path.relpath(path, out_dir).replace("\\", "/"),
            "messages": len(msgs),
            "approx_tokens": len(text) // 4,
            "restored": False,
        })

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {len(manifest)} transcripts to {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
