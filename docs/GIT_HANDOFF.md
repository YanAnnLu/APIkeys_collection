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
cd L:\RRKAL_project
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
gh run list --repo Kagamihara-Ruruka/APIkeys_collection --limit 5
gh run watch RUN_ID --repo Kagamihara-Ruruka/APIkeys_collection --exit-status
git status --short
```

If the push reaches `origin/main` but no GitHub Actions run appears for the pushed SHA after a few minutes, manually dispatch CI and then watch that run:

```bash
gh workflow run CI --repo Kagamihara-Ruruka/APIkeys_collection --ref main
gh run list --repo Kagamihara-Ruruka/APIkeys_collection --limit 8
gh run watch RUN_ID --repo Kagamihara-Ruruka/APIkeys_collection --exit-status
```

Manual dispatch is only a fallback for CI enqueue anomalies. It does not replace local smoke checks or the normal push-triggered CI evidence.

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

## Optional Local Pre-push Smoke

Before pushing, Windows contributors and agents can run the same fast local checks with one command:

```powershell
.\scripts\pre_push_smoke.cmd
```

This checks whitespace problems in the working tree, staged diff, and `upstream..HEAD` pending-push diff when an upstream branch exists. It then runs core `py_compile`, `py -B -m unittest discover -s tests`, `py -B APIkeys_collection.py --summary`, and the offline MVP demo smoke with a temp pycache folder. On this project it is usually much faster than waiting for a failed GitHub Actions queue, though the full test suite may take tens of seconds depending on disk and Python environment.

For agent sessions where token usage matters, prefer the brief wrapper:

```powershell
.\scripts\pre_push_smoke_brief.cmd
```

It writes the complete pre-push output under `state/logs/pre_push_smoke_*.log`, then prints only key status, failure, traceback, unittest, and MVP smoke lines. If an external summarizer such as `distill` is available, use it only on the saved log or selected tail, not as the source of truth. On Windows, call `distill.cmd` rather than `distill`; as of 2026-05-22, `@samuelfaj/distill@1.5.2` installs but cannot run on this machine because the npm registry does not publish the expected `@samuelfaj/distill-win32-x64` platform package. Treat `distill` as optional until `distill.cmd --version` succeeds.

To install it as this clone's local Git `pre-push` hook:

```powershell
.\scripts\install_pre_push_hook.cmd
```

Git hooks live under `.git/hooks/`, so this is intentionally local-only and is not pushed to GitHub. If a true emergency push is needed after reviewing the risk, use `git push --no-verify`; normal development should still watch GitHub Actions after push so the checkpoint has a remote CI record.

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

GitHub Actions runs a lightweight CI matrix on Ubuntu plus the explicit `windows-2025-vs2026` runner for pushes and
pull requests to `main`. It runs unit tests, `--summary`, and the offline MVP demo smoke with `PYTHONDONTWRITEBYTECODE=1` to avoid
platform-specific `.pyc` lock issues. The Windows label is pinned to the Visual Studio 2026 image so the project tests
the same Windows image GitHub is migrating `windows-latest` toward, instead of waiting for an implicit label switch.
On macOS, `gh` is installed; the account was renamed from `YanAnnLu` to `kagamihara-rururka`, then to `Kagamihara-Ruruka`, so use `Kagamihara-Ruruka/APIkeys_collection` after push to confirm CI, because GitHub mobile
notifications report workflow status, not whether `git push` reached the remote.
The workflow also supports `workflow_dispatch` so an agent can manually rerun CI when push-event enqueueing does not happen.

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
