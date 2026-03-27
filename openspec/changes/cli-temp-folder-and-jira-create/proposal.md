# Proposal: CLI Temp Folder & Jira Create Ticket

## Problem

Two separate issues in the kb-cli multi-step task execution system:

### 1. File Path Hallucination in CLI Mode

When one plan step writes a file and the next step reads it, the LLM often generates
an incorrect path for the read step — the filename is correct but the directory hierarchy
differs from what `write_file` actually wrote (e.g., writes to `output/report.md`, reads
from `report.md` or `data/report.md`). This causes `FileTool` to return `NOT_FOUND`.

Additionally, `FileTool.allowed_paths` does not include `output/` or `temp/`, causing
even correctly-pathed reads to be blocked with `ACCESS_DENIED`.

There is also no semantic distinction between temporary intermediate files (used between
steps) and final output files (the user's deliverable), leading to messy output directories.

### 2. Missing Jira Create Ticket Capability

The Jira tooling only supports reading (fetch, JQL search). There is no way to create
new Jira tickets from CLI mode or RAG mode.

## Proposed Solution

### 1. Temp Folder + File Path Fallback

Introduce a `temp/` folder under `data_folder` for intermediate files produced during
multi-step task execution. This folder is session-scoped and cleaned up automatically
when the task completes. The `output/` folder is reserved for user-requested final
deliverables only.

Add a basename-based fallback to `FileTool.read_file()`: when a file path is not found,
extract the filename and search `data_folder` subdirectories in priority order
(`temp/` → `output/` → `input/` → `source/` → `index/`), returning the most recently
modified match.

Also expand `FileTool.allowed_paths` to include `output_path` and `temp_path` so reads
from those directories are not blocked.

### 2. Jira Create Ticket Tool

Add a `jira_create_ticket` tool (available in both CLI and RAG mode) that creates a
Jira issue with inline user approval. The tool displays a ticket summary and prompts
`[Y/n]` before calling the API. Missing `project_key` falls back to a new
`jira_default_project` setting. Simple version: project + summary + description + issue_type.

## Non-Goals

- No changes to RAG-mode routing or graph nodes
- No Jira ticket update/comment/transition tools (future scope)
- No multi-file temp management UI — cleanup is automatic
- No file explorer for temp folder contents
