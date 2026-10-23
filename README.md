# Claude migration tools

Tools for moving the contents of a claude.ai data export (Settings → Privacy → Export data) into another account: conversations, projects, memory and artifacts.

claude.ai has no import, so these scripts turn the export into a restore kit of readable files that you bring back into the new account by hand or with browser automation.

Unzip the export first. `<export_dir>` below is the folder holding `conversations-000/`, `projects-000/`, `memories-000/` and `frames-000/`.

Both scripts use the standard library only (Python 3.8+).

## What the export contains

| Part | In the export | What you can restore |
|---|---|---|
| Conversations | Full messages | New chats started from a transcript, or transcripts uploaded as project knowledge |
| Projects | Name, description, instructions, knowledge **filenames** | Recreate the project, paste the instructions, re-upload knowledge files from your originals |
| Project knowledge files | Filenames only, **no contents** | Files Claude created in a chat are recovered; the rest must come from your own copies |
| Memory | Account memory, per-project memory, memory files | Full text |
| Artifacts | Titles, descriptions, version history, **no contents** | A list to find and re-create them; content created in chats is in the recovered files |

## convert_conversations.py

```bash
python -I convert_conversations.py <export_dir> <out_dir>
```

- `<out_dir>/<project name>/<date>_<title>.md`, one transcript per conversation; conversations outside any project go under `_no_project/`
- `<out_dir>/manifest.json`, listing each conversation's original id, title, project, file, message count, approximate token size and a `restored` flag for tracking progress

Only the active branch of each conversation is kept (the path ending at the most recent message), so edited or regenerated replies are dropped. Thinking blocks are left out. Tool calls and results are cut to one line, but files Claude created are kept in full. Empty conversations are skipped.

To restore a conversation, start a new chat in the matching project, attach its transcript and ask Claude to read it and continue from where it left off.

## export_account.py

```bash
python -I export_account.py <export_dir> <out_dir>
```

| Output | Use it to |
|---|---|
| `projects/<project>/instructions.md` | Paste into the new project's instructions |
| `projects/<project>/memory.md` | Restore that project's memory |
| `projects/<project>/knowledge_files.md` | Checklist of knowledge files to re-upload, with recovered copies marked |
| `projects/projects.json` | Summary of every project, with a `restored` flag |
| `memory/account_memory.md` | Restore memory from chats outside projects |
| `memory/files/...` | Memory files at their original paths |
| `artifacts/artifacts.md` | List of artifacts and pages with titles, descriptions and versions |
| `recovered_files/<project>/<conversation>/...` | Every file Claude wrote with `create_file`, last version per path |

## Suggested order

1. Run both scripts.
2. Recreate each project: name, description, `instructions.md`, then knowledge files from `knowledge_files.md`.
3. Restore memory: paste `account_memory.md` and each project's `memory.md` into the new account's memory, or ask Claude to remember them.
4. Restore conversations from the transcripts into their projects.
5. Re-create the artifacts you still need using `artifacts.md` and `recovered_files/`.

## Privacy

Exports and generated output contain your full chat history. Keep them out of this repository; `.gitignore` excludes the usual export and output folders.
