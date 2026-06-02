---
name: mdp-file-safety
description: Use when creating, editing, moving, copying, or deleting files in an MDP-managed project with no-clobber safety requirements.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mdp, files, safety, no-clobber, rollback]
    related_skills: [mdp-verification-rollback, mdp-repo-permission-modes, repository-organization]
---

# MDP File Safety

## Overview

MDP-managed work is no-clobber by default. Agents must not silently overwrite files, erase user work, or make broad edits without inspection. This skill defines safe file creation and editing behavior.

The standard is simple: inspect first, edit narrowly, preserve rollback, and make replacements explicit.

## When to Use

Use this skill when:

- Creating new files or directories.
- Editing existing files.
- Moving, copying, renaming, or deleting files.
- Working on Windows-mounted paths under `/mnt/c`, `/mnt/d`, or similar.
- Generating scripts that write files.
- Installing shared skills, templates, configs, or project artifacts.

## Core Rules

1. Before creating a file, check whether the target path exists.
2. Use exclusive creation for new files.
3. Use targeted patches for existing files.
4. Do not use blind full-file writes on existing project files unless overwrite is explicitly authorized.
5. If overwriting matters, create a backup or have a clear rollback path.
6. State what will be replaced when replacing existing content.
7. Treat Windows-mounted paths as case-insensitive.

## Safe Creation Patterns

Python:

```python
from pathlib import Path
with Path(path).open('x', encoding='utf-8') as f:
    f.write(content)
```

Shell:

```bash
set -o noclobber
[ ! -e "$path" ] && printf '%s' "$content" > "$path"
```

Agent tools:

- Search for the target first.
- Read the relevant area if the file exists.
- Use targeted `patch` for edits.
- Use `write_file` only for confirmed new files or approved full replacements.

## Overwrite Approval Standard

Overwriting is allowed only when all are true:

1. Existing file was inspected or its purpose is known.
2. Overwrite was explicitly requested or approved.
3. The agent states what will be replaced.
4. Backup, diff, or rollback exists when the file matters.

## Windows Path Warning

Under Windows mounts, `AGENTS.md` and `agents.md` can refer to the same file. Normalize or compare paths case-insensitively before creating files whose names differ only by case.

## Common Pitfalls

1. **Using full-file writes for convenience.** Patch existing files unless full replacement is the explicit task.
2. **Assuming Linux case sensitivity under `/mnt/c`.** Windows mounts can collide by case.
3. **Copying shared skills over profile skills without checking.** Check for shadows and backups first.
4. **Deleting before verification.** Move to backup when safe, then verify.
5. **No rollback path.** Meaningful implementation changes need rollback notes.

## Verification Checklist

- [ ] Target paths were checked before creation.
- [ ] Existing files were edited with targeted patches or approved overwrite.
- [ ] Important replacements have backups, diffs, or rollback notes.
- [ ] Windows-mounted paths were treated as case-insensitive.
- [ ] Final report lists files created, changed, moved, or backed up.
