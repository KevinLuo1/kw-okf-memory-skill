# KW-OKF Memory Skill

Local-first, audited long-term memory for Codex.

KW-OKF Memory is a Codex Skill that helps Codex preserve, retrieve, and maintain durable knowledge in a local Markdown vault. It uses an OKF-style schema, staged writes, rebuildable indexes, lightweight association checks, and optional Obsidian review so memory stays useful without becoming an opaque black box.

## Why This Exists

LLM conversations are great at short-term reasoning and terrible at staying organized across weeks of work. This Skill gives Codex a disciplined memory workflow:

- Keep knowledge in plain Markdown files you can read and edit.
- Require staged previews before formal wiki writes.
- Separate Skill instructions from personal or project knowledge.
- Rebuild search and graph indexes from source files instead of trusting generated state.
- Support lightweight lookup, deeper synthesis, association cleanup, and periodic maintenance.

## Highlights

- **Local-first vault**: your knowledge lives in a normal folder, not inside the Skill package.
- **Audited write path**: formal writes follow `stage -> preview -> confirmation -> commit -> build/audit`.
- **OKF page schema**: each wiki page has structured frontmatter, parent routing, source references, review dates, and an evolution log.
- **Search and think modes**: quick lookup when the answer is direct, deeper synthesis when links, conflicts, or stale knowledge matter.
- **Association workflow**: check duplicates, add useful relative Markdown links, find orphan pages, and inspect conflicts.
- **Obsidian-friendly**: the vault remains standard Markdown and can be reviewed in Obsidian after commit.
- **Bilingual-ready**: defaults to `en-US`, with `zh-CN` supported for users who work in Chinese.

## Install In Codex

After this repository is on GitHub, ask Codex to install the Skill from the Skill folder:

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
python scripts/okf_glue.py search --vault ~/KnowledgeBase --query "example"
```

For formal writes, let Codex follow the Skill workflow. The important rule is simple: preview first, commit only after confirmation.

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

KW-OKF Memory is intentionally conservative:

- It does not treat Obsidian as the write authority.
- It does not make generated JSON the source of truth.
- It does not silently create new top-level framework folders.
- It does not require a background daemon.
- It keeps formal wiki writes behind preview and confirmation.

## Status

This is an early public release intended for Codex users who want a transparent, Markdown-based long-term memory workflow. Feedback, issues, and improvements are welcome.