# Git Handoff Guide

Use this project as the handoff unit between Mac and Windows.

## First-Time Setup

On macOS:

```bash
cd APIkeys_collection
git init
git add .
git commit -m "Initialize APIkeys_collection launcher"
```

On Windows PowerShell, after Git is installed:

```powershell
cd K:\APIkeys_collection
.\scripts\setup_git.ps1 -UserName "Your Name" -UserEmail "you@example.com"
git status --short --branch
```

GitHub CLI authentication, once per machine:

```bash
gh auth login
gh auth status
```

If the project folder is on a synced or network drive and Git reports dubious ownership:

```bash
git config --global --add safe.directory "<absolute project path>"
```

## Daily Handoff Loop

Before switching machines:

```bash
git status --short
git add APIkeys_collection.py APIkeys_collection_ui.py api_launcher tests README.md docs catalog config scripts .gitignore .gitattributes
git commit -m "Describe the launcher change"
git push origin main
gh run list --repo YanAnnLu/APIkeys_collection --limit 5
gh run watch RUN_ID --repo YanAnnLu/APIkeys_collection --exit-status
git status --short
```

After switching machines:

```bash
git pull origin main
git status --short --branch
python3 -m py_compile APIkeys_collection.py APIkeys_collection_ui.py
python3 -m unittest discover -s tests
python3 APIkeys_collection.py --summary
```

On Windows, replace `python3` with `py`:

```powershell
git pull origin main
py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py
py -m unittest discover -s tests
py APIkeys_collection.py --summary
```

On the current macOS Codex handoff environment, prefer the project env rather than base Python:

```bash
conda run -n metal_trade_312 python -m unittest discover -s tests
```

Generate a handoff report for humans or another agent:

```powershell
py APIkeys_collection.py --handoff-report state\handoff.md --manifest-health --show-logs 10
```

The report includes Git status, current HEAD, catalog counts, manifest health, last verification timestamps, open GTD focus items, recent structured logs, portal/local-discovery summaries, and suggested resume checks.

For cross-Agent handoff, update and read `docs/AGENT_HANDOFF.zh-TW.md` first. It is the short, fixed handoff card; this file remains the longer Git workflow guide.

GitHub Actions runs a lightweight CI matrix on Windows and Ubuntu for pushes and pull requests to `main`. It runs unit
tests and a CLI smoke check with `PYTHONDONTWRITEBYTECODE=1` to avoid platform-specific `.pyc` lock issues.
On macOS, `gh` is installed and authenticated as `YanAnnLu`; use it after push to confirm CI, because GitHub mobile
notifications report workflow status, not whether `git push` reached the remote.

If Windows CI fails with `PermissionError: [WinError 32]` around `*.sqlite` in a temp directory, check for unclosed
SQLite connections. Python's `with sqlite3.connect(...)` manages transactions but does not close the connection; use
`contextlib.closing(sqlite3.connect(...))` for short-lived probes/tests.

Chinese setup notes for Windows/macOS/Linux live in `docs/SETUP.zh-TW.md`.

If the project is on a synced Windows drive and `.pyc` writes are locked, use:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
py -m py_compile APIkeys_collection.py APIkeys_collection_ui.py
```

## What To Avoid

- Do not commit filled `*.private.json`, `*.secret.json`, or real `.env` files.
- Avoid editing the same file on both machines before committing.
- Avoid simultaneous SQLite writes from Mac and Windows through a synced drive.
- Do not rely on chat history as the only handoff memory. Put decisions in `docs/PROJECT_STATE.md`.

## Good Commit Messages

- `Refactor provider registry into data module`
- `Add launcher download state model`
- `Wire Tk UI to provider repository`
- `Add GEBCO dataset adapter skeleton`
