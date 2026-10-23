# Claude migration tools

Tools for moving the contents of a claude.ai data export (Settings → Privacy → Export data) into another account.

claude.ai has no import for past conversations, so the approach is to turn each conversation into a Markdown transcript and start a new chat from it (attach the transcript and ask Claude to pick up where it left off), or upload the transcripts as project knowledge.

## convert_conversations.py

Converts `conversations-000/conversations.json` into one Markdown file per conversation, grouped into folders by project.

```bash
python -I convert_conversations.py <export_dir> <out_dir>
```

`<export_dir>` is the folder holding the unzipped `conversations-000/` and `projects-000/` folders.

Output:

- `<out_dir>/<project name>/<date>_<title>.md`, with conversations outside any project under `_no_project/`
- `<out_dir>/manifest.json`, listing each conversation's original id, title, project, file, message count, approximate token size and a `restored` flag for tracking progress

Notes:

- Only the active branch of each conversation is kept (the path ending at the most recent message), so edited or regenerated replies are dropped.
- Thinking blocks are left out. Tool calls and results are cut to one line, but files Claude created (`create_file`) are kept in full.
- Empty conversations are skipped.
- Standard library only, Python 3.8+.

## Privacy

Exports and transcripts contain your full chat history. Keep them out of this repository; `.gitignore` excludes the usual export and output folders.
