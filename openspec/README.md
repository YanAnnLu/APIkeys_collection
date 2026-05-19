# OpenSpec Workspace

This directory is the Git-tracked specification workspace for APIkeys_collection.

- `specs/` contains current product and engineering capabilities.
- `changes/` contains active proposals/tasks/design notes before implementation.
- `changes/archive/` contains completed changes after verification.

For this project, OpenSpec is mandatory for medium or risky cross-module work, but small bug fixes can remain lightweight if the handoff/GTD/docs are updated afterward.

Useful commands:

```bash
npx -y @fission-ai/openspec@latest list --specs
npx -y @fission-ai/openspec@latest validate --all --no-interactive
```

Spectra can be used as a GUI over this folder, but the files in Git remain the source of truth.
