# KW-OKF Memory Skill

Turn Codex conversations into a durable local memory system.

KW-OKF Memory is a Codex Skill for people who want Codex to remember project decisions, operating rules, research notes, assets, and hard-won lessons across chats without dumping everything into a messy folder. It gives Codex a disciplined way to capture useful knowledge, preview it, commit it into a local Markdown vault, rebuild indexes, and retrieve it later for search or deeper reasoning.

Instead of treating memory as hidden model state, this Skill keeps memory transparent: plain Markdown files, structured frontmatter, relative links, audit logs, rebuildable JSON indexes, and optional Obsidian review.

## The Problem It Solves

Codex can help in the moment, but long-running work has a memory problem:

- Important decisions get buried in old chats.
- Project rules are repeated, forgotten, or contradicted.
- Useful screenshots and source notes are hard to connect to later work.
- Knowledge bases become messy when AI writes directly into them without review.
- Search alone is not enough when you need Codex to compare, synthesize, or detect conflicts.

KW-OKF Memory gives Codex a workflow for turning those scattered fragments into an organized local knowledge vault.

## What It Does

Use this Skill when you want Codex to:

- Save a conversation lesson, decision, rule, SOP, case, entity note, or source note.
- Create or update a structured OKF-style Markdown page.
- Stage a draft first, show a preview, and only commit after confirmation.
- Build `categories.json` for fast lookup and `graph.json` for parent/link relationships.
- Search existing memory before answering or writing new notes.
- Use a deeper think flow when a question needs related context, conflicts, stale-note checks, or synthesis.
- Process screenshots and other assets into a predictable local vault structure.
- Audit the vault for duplicate notes, broken links, orphan pages, stale records, and missing metadata.
- Open committed notes in Obsidian for human review without making Obsidian the write authority.

## Why It Is Different

KW-OKF Memory is intentionally boring in the best way:

- **Local-first**: your memory lives in your filesystem.
- **Human-readable**: Markdown pages and assets are the source of truth.
- **Audited**: formal writes go through staging, preview, confirmation, commit, build, and audit.
- **Agent-friendly**: structured frontmatter and indexes make it easier for Codex to locate the right memory quickly.
- **Not a black box**: generated JSON can be rebuilt from Markdown at any time.
- **Obsidian-compatible**: review and navigate the vault with normal Markdown tooling.
- **Bilingual-ready**: defaults to `en-US`, with `zh-CN` supported for Chinese workflows.

## Core Workflow

```text
User / Codex conversation
        |
        v
Search existing memory when relevant
        |
        v
Stage a draft in inbox/staged/
        |
        v
Preview + user confirmation
        |
        v
Commit to wiki/
        |
        v
Rebuild categories.json + graph.json
        |
        v
Audit + optional Obsidian review
```

The key rule is simple: Codex can help write memory, but formal knowledge does not enter `wiki/` silently.

## Install In Codex

Ask Codex to install the Skill from this repository:

```text
Use skill-installer to install https://github.com/KevinLuo1/kw-okf-memory-skill/tree/main/skills/kw-okf-memory
```

Restart Codex after installation so the Skill is discovered.

## Configure

The public release uses safe defaults:

```json
{
  "vault_path": "~/KnowledgeBase",
  "default_language": "en-US",
  "fallback_language": "en-US",
  "supported_languages": ["en-US", "zh-CN"],
  "language_mode": "follow-user-language",
  "obsidian_auto_open_after_commit": false
}
```

Edit `skills/kw-okf-memory/config.json` after installation, or pass `--vault <path>` to the glue script commands.

## Quick Start

Initialize a vault:

```bash
python scripts/okf_glue.py init --vault ~/KnowledgeBase
```

Build indexes and audit the vault:

```bash
python scripts/okf_glue.py build --vault ~/KnowledgeBase
python scripts/okf_glue.py audit --vault ~/KnowledgeBase
```

Search existing knowledge:

```bash
python scripts/okf_glue.py search --vault ~/KnowledgeBase --query "pricing decision"
```

In normal use, you can talk to Codex naturally:

```text
Save this decision to long-term memory.
Search my memory for previous rules about this project.
Think with my memory before answering this design question.
Audit my memory vault for duplicates and stale notes.
```

## What The Vault Contains

A generated vault uses this shape:

```text
index.md                 # root router
log.md                   # append-only audit log
categories.json          # rebuildable category/node index
graph.json               # rebuildable parent/link graph
tags.md                  # human-readable tag registry
inbox/                   # raw and staged inputs
assets/                  # images, documents, screenshots, references
wiki/                    # formal knowledge pages
```

`categories.json` and `graph.json` are rebuildable outputs. Markdown pages and assets are the source of truth.

## Repository Layout

```text
skills/kw-okf-memory/              # installable Codex Skill
skills/kw-okf-memory/SKILL.md      # entry instructions loaded by Codex
skills/kw-okf-memory/config.json   # default public configuration
skills/kw-okf-memory/references/   # workflow and schema references
skills/kw-okf-memory/scripts/      # deterministic glue tooling
```

Do not store personal vault content inside this repository. The Skill defines protocol and tools; your vault stores the knowledge.

## Safety Model

KW-OKF Memory is conservative by design:

- It does not treat Obsidian as the write authority.
- It does not make generated JSON the source of truth.
- It does not silently create new top-level framework folders.
- It does not require a background daemon.
- It keeps formal wiki writes behind preview and confirmation.

## Status

This is an early public release for Codex users who want transparent, Markdown-based long-term memory. Feedback, issues, and improvements are welcome.
