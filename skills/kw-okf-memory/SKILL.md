---
name: kw-okf-memory
description: Build and maintain a structured Obsidian-friendly Markdown memory wiki for Codex using a Karpathy-style wiki, Google OKF-inspired schema, rebuildable categories.json and graph.json indexes, safe structure evolution, and staged AI writes. Use when Codex should save, update, retrieve, synthesize, search, stage, commit, audit, or maintain durable project memory; prevent messy AI-written knowledge bases; check duplicates, conflicts, stale notes, broken links, associations, and vault structure; or open committed notes in Obsidian for human review.
---

# KW-OKF Memory

## Core Boundary

Use this skill to maintain a long-term Codex memory wiki that stays structured, can evolve safely, supports index-and-graph retrieval, and prevents silent AI writes. Recommend Obsidian for human review, search, backlinks, and navigation after commit, but keep Markdown and the glue script as the write/audit authority.

Keep the boundary clear: the Skill stores tools and protocol, the Vault stores long-term knowledge assets, the Python glue layer performs deterministic filesystem/index/audit work, and Codex extracts, judges, previews, and asks for confirmation.

## Task Routing

- For preservation or write intents, including saving experience/rules/cases, distilling knowledge, creating or updating OKF pages, or updating long-term memory, read `references/write_workflow.md` plus `references/okf_schema.md`, `references/vault_framework.md`, and `references/association_workflow.md` as needed.
- For lookup intents that need specific existing records, read `references/retrieval_workflow.md` and use `search`.
- For synthesis, judgment, planning, conflict-check, comparison, or lesson-extraction intents that need prior memory, read `references/retrieval_workflow.md` and use `think`.
- For maintenance intents involving vault health, duplicates, conflicts, stale notes, orphan pages, missing links, or deep organization, read `references/maintenance_workflow.md`.
- For memory asset processing intents, use `process-img` and follow the asset path rules in `references/vault_framework.md`.
- Use `obsidian-open` / `obsidian-search` only for human review. Obsidian is not the write or audit authority.

## Load As Needed

- `config.json`: read before filesystem actions to locate the Vault, language policy, Obsidian settings, and directory confirmation rules.
- `references/write_workflow.md`: formal writes, preview, confirmation, commit, and existing-knowledge updates.
- `references/okf_schema.md`: OKF node types, frontmatter fields, body template, and source refs.
- `references/vault_framework.md`: fixed Vault skeleton, path safety, and directory creation rules.
- `references/retrieval_workflow.md`: `search` / `think` mode selection, synthesis, gap analysis, and staleness checks.
- `references/association_workflow.md`: lightweight write-time associations, relationship labels, and deep association cleanup.
- `references/maintenance_workflow.md`: manual maintenance flow, command roles, duplicate/conflict/staleness/orphan checks.
- `references/wiki_lookup_workflow.md`: wiki-style lookup, small reads, link following, and error-book rules.

## Command Entry

Use the glue script for deterministic filesystem work:

```bash
python scripts/okf_glue.py <command> [options]
```

Common commands are `init`, `build`, `audit`, `search`, `stage`, `commit`, `process-img`, `obsidian-open`, and `obsidian-search`; before running a command, read the task-specific workflow reference and confirm arguments with `python scripts/okf_glue.py <command> --help`.

## Language Policy

- When writing formal notes, use the same language as the current user-Codex conversation unless the user explicitly requests another supported language. When unclear, use the configured fallback language, which defaults to `en-US` in this public release.

## Hard Rules

- Never write a formal `wiki/` page without preview and explicit user confirmation.
- Formal writes must follow `stage -> preview -> user confirmation -> commit -> build/audit`.
- A user may grant batch confirmation for one clearly scoped ordinary cleanup task; batch confirmation does not cover framework changes, schema changes, formal-knowledge deletion, or large merges.
- Store formal knowledge only in the Vault; do not store business knowledge in the Skill folder.
- Create runtime business directories or missing Routers only when previewed and confirmed.
- Treat new top-level directories and new `wiki/` first-level categories as framework changes that require explicit user confirmation and framework doc updates.
