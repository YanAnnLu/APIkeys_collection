# development-workflow Specification

## Purpose

This capability defines how the project uses OpenSpec-aligned development to reduce handoff risk while keeping the backend MVP moving.

## Requirements

### Requirement: OpenSpec Path For Cross-Module Changes

The project SHALL require an OpenSpec-style proposal, task list, acceptance criteria, and risk notes before implementing medium or risky cross-module changes.

#### Scenario: Cross-module backend feature

- GIVEN a change touches crawler, adapter, download plan, import, registry, UI, external integration, or cross-platform setup
- WHEN an agent starts implementation
- THEN the agent SHALL record scope, tasks, acceptance criteria, and known risks in `openspec/changes/` or in the documented transition workflow before editing production code.

#### Scenario: Small safe fix

- GIVEN a change is a narrow bug fix, typo, parser tweak, or focused test update
- WHEN the change does not alter data models, UI information architecture, external integrations, or destructive actions
- THEN the agent MAY implement directly, but SHALL update GTD, handoff, or related documentation if project state changes.

### Requirement: Git-Tracked Specification Source Of Truth

The project SHALL treat Git-tracked OpenSpec files and documentation as the source of truth for development state.

#### Scenario: Spectra GUI is used

- GIVEN Spectra is used to inspect or manage specs
- WHEN a task state, proposal, or requirement changes
- THEN the corresponding files under `openspec/` SHALL be updated and committed, rather than leaving state only inside a GUI session.

### Requirement: OpenSpec Language Policy / OpenSpec 語言規則

The project SHALL allow Traditional Chinese prose inside OpenSpec specs, changes, tasks, design notes, risks, and acceptance criteria.

#### Scenario: Team-facing workflow rule

- GIVEN a rule is meant for the current human team and future agents working in this repository
- WHEN the rule explains intent, workflow boundaries, acceptance criteria, risks, or handoff notes
- THEN the rule SHOULD be written in Traditional Chinese or bilingual Chinese/English so maintainers can read it without extra translation.

#### Scenario: Tool-facing identifiers

- GIVEN a field, file path, capability id, command, CLI flag, product name, or OpenSpec structural marker is consumed by tools or searched by agents
- WHEN writing the OpenSpec artifact
- THEN the identifier SHOULD remain stable ASCII/English, while the explanatory prose MAY be Traditional Chinese.

### Requirement: OpenSpec As Project Habit Memory

The project SHALL use OpenSpec as the durable home for development habits, workflow contracts, acceptance criteria, and cross-agent process rules that are too broad to live only in one agent skill.

#### Scenario: A recurring development habit is discovered

- GIVEN the team identifies a recurring habit such as checkpoint logging, UI hardening boundaries, docs synchronization, or evidence requirements
- WHEN the habit affects future medium or repeated work
- THEN the agent SHOULD record it in an OpenSpec requirement, change, or task before or alongside skill updates.

#### Scenario: Skill and OpenSpec overlap

- GIVEN a skill tells an agent how to act during a session
- WHEN the rule is also a durable project policy
- THEN the skill SHOULD point to the relevant OpenSpec capability or docs route, and OpenSpec SHALL remain the versioned project contract.

### Requirement: Portable Workflow Pattern

The project SHALL keep its development workflow separable enough that the same governance pattern can be reused in other repositories without copying APIkeys_collection-specific domain rules.

#### Scenario: Workflow is copied to another project

- GIVEN another repository wants to reuse this development style
- WHEN preparing the reusable starter set
- THEN the agent SHOULD copy the workflow shape: project GTD, agent handoff, development log, docs index, OpenSpec workspace, project skill, local smoke checks, and checkpoint reporting rules.
- AND the agent SHALL remove or rewrite APIkeys_collection-specific dataset, crawler, provider, Qt, database, renderer, and path rules before using the workflow in the other repository.

#### Scenario: A new project is small

- GIVEN the target repository has not yet developed cross-module risk
- WHEN introducing OpenSpec
- THEN the agent SHOULD start with only a `development-workflow` capability and add domain-specific capabilities only after repeated or risky work justifies them.

### Requirement: MVP-First Process

The workflow SHALL reduce rework and handoff cost without blocking the backend MVP loop.

#### Scenario: Process becomes heavier than the change

- GIVEN a change can be completed and verified in a small local step
- WHEN writing a full proposal would take longer than the implementation and verification
- THEN the agent SHALL keep the process lightweight and document only the durable decision or result.

### Requirement: Tooling Isolation

OpenSpec, Spectra, Qt Creator, and Qt Designer setup SHALL respect the project environment boundaries and SHALL distinguish workstation-specific tooling from cross-platform project facts.

#### Scenario: Python or Qt tooling is needed on macOS

- GIVEN a Python or Qt-related tool is required
- WHEN installing or running that tool
- THEN the agent SHALL prefer `metal_trade_312` and SHALL NOT install Python packages into base or system Python.

#### Scenario: Python or Qt tooling is checked on Windows

- GIVEN the project is running on the Windows workstation
- WHEN an agent needs UI tooling facts
- THEN the agent SHALL run `scripts\check_ui_tooling.cmd` or update its equivalent before assuming Qt Creator, PySide6, or a named Conda environment exists.

#### Scenario: Spectra GUI is installed on macOS

- GIVEN Spectra is installed for this workstation
- WHEN installation location is chosen
- THEN the app SHALL live in user-owned `~/Applications/Spectra.app` unless the user explicitly asks for a system-wide install.

#### Scenario: Spectra GUI is available on Windows

- GIVEN Spectra is installed for this workstation
- WHEN an agent needs to inspect or organize OpenSpec artifacts
- THEN the agent MAY use `C:\Users\lyn59\AppData\Local\Spectra\spectra.exe`, while keeping Git-tracked OpenSpec files as the authority.

### Requirement: Beginner-Friendly Progress Reporting

Agents SHALL describe OpenSpec/process changes in beginner-friendly language.

#### Scenario: Reporting a tooling or workflow checkpoint

- GIVEN the user asks to continue development
- WHEN the agent reports progress
- THEN the report SHALL explain what changed, why it matters, and how much it affects the remaining MVP work in plain Traditional Chinese.
