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

### Requirement: MVP-First Process

The workflow SHALL reduce rework and handoff cost without blocking the backend MVP loop.

#### Scenario: Process becomes heavier than the change

- GIVEN a change can be completed and verified in a small local step
- WHEN writing a full proposal would take longer than the implementation and verification
- THEN the agent SHALL keep the process lightweight and document only the durable decision or result.

### Requirement: Tooling Isolation

OpenSpec, Spectra, and Qt Designer setup SHALL respect the project environment boundaries.

#### Scenario: Python or Qt tooling is needed on macOS

- GIVEN a Python or Qt-related tool is required
- WHEN installing or running that tool
- THEN the agent SHALL prefer `metal_trade_312` and SHALL NOT install Python packages into base or system Python.

#### Scenario: Spectra GUI is installed on macOS

- GIVEN Spectra is installed for this workstation
- WHEN installation location is chosen
- THEN the app SHALL live in user-owned `~/Applications/Spectra.app` unless the user explicitly asks for a system-wide install.

### Requirement: Beginner-Friendly Progress Reporting

Agents SHALL describe OpenSpec/process changes in beginner-friendly language.

#### Scenario: Reporting a tooling or workflow checkpoint

- GIVEN the user asks to continue development
- WHEN the agent reports progress
- THEN the report SHALL explain what changed, why it matters, and how much it affects the remaining MVP work in plain Traditional Chinese.
