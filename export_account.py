"""Turn a claude.ai data export into a restore kit for projects, memory and artifacts.

Usage: python -I export_account.py <export_dir> <out_dir>

Writes:
  <out_dir>/projects/<project>/instructions.md   project instructions (paste into the new project)
  <out_dir>/projects/<project>/memory.md         project memory, if any
  <out_dir>/projects/<project>/knowledge_files.md checklist of knowledge files to re-upload
  <out_dir>/projects/projects.json               machine-readable summary
  <out_dir>/memory/account_memory.md             memory from chats outside projects
  <out_dir>/memory/files/...                     memory files, at their original paths
  <out_dir>/artifacts/artifacts.md               artifact and page titles, versions, descriptions
  <out_dir>/recovered_files/<project>/<conversation>/...  files Claude created in chats

The export holds only the filenames of project knowledge files and only the
metadata of artifacts, not their contents. Files Claude wrote with create_file
are recovered from the conversations (last version written wins), and knowledge
files with a matching filename are marked as recovered in the checklist.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir
from convert_conversations import active_branch, safe_name  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def safe_rel_path(p):
    parts = [safe_name(x, 100) for x in p.replace("\\", "/").split("/") if x not in ("", ".", "..")]
    return os.path.join(*parts) if parts else "untitled"


def recover_created_files(convos, projects, out_dir):
    """Write every file Claude created in a chat; return {basename: [relative paths]}."""
    found = {}
    for c in convos:
        latest = {}
        for m in active_branch(c.get("chat_messages") or []):
            for b in m.get("content") or []:
                inp = b.get("input") if b.get("type") == "tool_use" and b.get("name") == "create_file" else None
                if isinstance(inp, dict) and inp.get("path"):
                    latest[inp["path"]] = inp.get("file_text") or inp.get("content") or ""
        if not latest:
            continue
        proj = projects.get(c.get("project_uuid") or "")
        base = os.path.join(out_dir, "recovered_files", safe_name(proj["name"]) if proj else "_no_project",
                            f"{c['created_at'][:10]}_{safe_name(c.get('name') or 'Untitled', 60)}")
        for path, body in latest.items():
            dest = os.path.join(base, safe_rel_path(path))
            write(dest, body)
            found.setdefault(os.path.basename(path).lower(), []).append(os.path.relpath(dest, out_dir).replace("\\", "/"))
    return found


def export_projects(projects, memory, recovered, out_dir):
    summary = []
    for p in sorted(projects.values(), key=lambda p: p["created_at"]):
        folder = os.path.join(out_dir, "projects", safe_name(p["name"]))
        write(os.path.join(folder, "instructions.md"), (p.get("prompt_template") or "").strip() + "\n")

        proj_mem = (memory.get("project_memories") or {}).get(p["uuid"])
        if proj_mem:
            write(os.path.join(folder, "memory.md"), f"# Project memory: {p['name']}\n\n{proj_mem.strip()}\n")

        lines = [f"# Knowledge files: {p['name']}", "",
                 "The export lists these files but does not include their contents.",
                 "Re-upload each one from your originals. Files marked recovered were found in a chat.", ""]
        n_recovered = 0
        for d in sorted(p.get("docs") or [], key=lambda d: d["filename"].lower()):
            hits = recovered.get(os.path.basename(d["filename"]).lower())
            if hits:
                n_recovered += 1
                lines.append(f"- [ ] {d['filename']} — recovered: `{hits[-1]}`")
            else:
                lines.append(f"- [ ] {d['filename']}")
        if not p.get("docs"):
            lines.append("_(no knowledge files)_")
        write(os.path.join(folder, "knowledge_files.md"), "\n".join(lines) + "\n")

        summary.append({
            "uuid": p["uuid"],
            "name": p["name"],
            "description": p.get("description") or "",
            "folder": os.path.relpath(folder, out_dir).replace("\\", "/"),
            "has_instructions": bool((p.get("prompt_template") or "").strip()),
            "has_memory": bool(proj_mem),
            "knowledge_files": len(p.get("docs") or []),
            "knowledge_files_recovered": n_recovered,
            "restored": False,
        })
    write(os.path.join(out_dir, "projects", "projects.json"), json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def export_memory(memory, out_dir):
    if memory.get("conversations_memory"):
        write(os.path.join(out_dir, "memory", "account_memory.md"),
              "# Account memory\n\n" + memory["conversations_memory"].strip() + "\n")
    for f in memory.get("memory_files") or []:
        write(os.path.join(out_dir, "memory", "files", safe_rel_path(f["path"])), f.get("content") or "")
    return len(memory.get("memory_files") or [])


def export_artifacts(export_dir, out_dir):
    arts = [load(f) for f in glob.glob(os.path.join(export_dir, "frames-000", "artifacts", "*", "artifact.json"))]
    lines = ["# Artifacts", "",
             "The export holds only artifact metadata, not content. Use this list to find and re-create them.", ""]
    for a in sorted(arts, key=lambda a: a.get("updated_at") or ""):
        versions = sorted(a.get("versions") or [], key=lambda v: v.get("created_at") or "")
        active = next((v for v in versions if v["id"] == a.get("active_version")), versions[-1] if versions else {})
        lines += [f"## {active.get('title') or 'Untitled'}", "",
                  f"- Kind: {a.get('kind')} · Visibility: {a.get('visibility')} · Updated: {(a.get('updated_at') or '')[:16]}",
                  f"- Versions: {len(versions)}"]
        if active.get("description"):
            lines.append(f"- Description: {active['description'].strip()}")
        for v in versions:
            lines.append(f"  - {v.get('created_at', '')[:16]} — {v.get('title') or ''}")
        lines.append("")
    write(os.path.join(out_dir, "artifacts", "artifacts.md"), "\n".join(lines))
    return len(arts)


def main(export_dir, out_dir):
    projects = {p["uuid"]: p for p in map(load, glob.glob(os.path.join(export_dir, "projects-000", "projects", "*.json")))}
    mem_files = glob.glob(os.path.join(export_dir, "memories-000", "memories", "*.json"))
    memory = load(mem_files[0]) if mem_files else {}
    convos = load(os.path.join(export_dir, "conversations-000", "conversations.json"))

    recovered = recover_created_files(convos, projects, out_dir)
    summary = export_projects(projects, memory, recovered, out_dir)
    n_mem_files = export_memory(memory, out_dir)
    n_arts = export_artifacts(export_dir, out_dir)

    total_docs = sum(s["knowledge_files"] for s in summary)
    got_docs = sum(s["knowledge_files_recovered"] for s in summary)
    print(f"Projects: {len(summary)} (knowledge files listed: {total_docs}, recovered from chats: {got_docs})")
    print(f"Project memories: {sum(s['has_memory'] for s in summary)} · account memory: {bool(memory.get('conversations_memory'))} · memory files: {n_mem_files}")
    print(f"Files recovered from chats: {sum(len(v) for v in recovered.values())}")
    print(f"Artifacts listed: {n_arts}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
