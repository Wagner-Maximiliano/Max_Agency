# Contributing to Max Agency

> **License note:** This repository does not yet have a license file. Until one is added, all rights are reserved — it is not legally reusable by others. Contributions are welcome but cannot be merged until a license is chosen. See [README.md](README.md) for context.

## What this project is

Max Agency is the *engine*, not a project. It provides the agent prompts, scripts, and coordination layer. Actual project work happens in separate project repos that Max Agency manages. Keep that distinction in mind — changes here affect every project the engine runs.

## How to contribute

1. Fork the repo and create a branch: `fix/short-description` or `feat/short-description`.
2. Make your change. Keep it small and focused — one thing per PR.
3. Test it against a real project repo: run `orchestrator-mechanics.sh` manually, verify no Python tracebacks.
4. Open a PR with a one-paragraph description of what changed and why.

## Ground rules

- **Never hardcode personal paths or usernames.** Use `$env:USERPROFILE` (Windows) or `$HOME` (WSL/bash).
- **Docs must match the code.** If you change a script behaviour, update the relevant doc in the same PR.
- **Labels matter.** `scripts/setup.ps1` defines the canonical label set — if you add a label the pipeline uses, add it there too.
- **No half-finished work.** If it breaks the pipeline, it shouldn't merge.

## Questions?

Open a GitHub Issue with the `question` label.
