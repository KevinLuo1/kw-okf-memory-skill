# KW-OKF Memory Skill

A Codex Skill for keeping AI-written knowledge bases organized across chats.

KW-OKF Memory helps Codex preserve useful project context without turning your knowledge base into a mess. It solves three common problems: Codex forgets context across chats, AI can write notes too freely, and local knowledge bases become chaotic as decisions, rules, screenshots, sources, and procedures pile up.

The Skill gives Codex a controlled workflow for saving durable knowledge into an Obsidian-friendly local Markdown vault. New memory is staged first, previewed for human confirmation, then committed into a Karpathy-style personal wiki with a Google OKF-inspired page schema. Codex can later search it, think with it, update it, and audit it.

Obsidian is recommended for human review and navigation, but it is not required. The core system is plain Markdown plus the bundled glue script.

## The Pain Points

Use this Skill when your Codex work has any of these problems:

- **Codex loses context across chats**: decisions, preferences, and lessons stay buried in old conversations.
- **AI writes too freely**: generated notes can duplicate, conflict, drift, or land in the wrong folder.
- **The knowledge base gets messy**: screenshots, sources, rules, cases, and procedures accumulate without a stable structure.
- **Search is not enough**: sometimes Codex needs linked context, stale-note checks, conflict checks, or synthesis before answering.

KW-OKF Memory turns loose chat context into an auditable local knowledge base that both humans and Codex can inspect.

## How It Solves Them

| Pain point | How KW-OKF Memory addresses it |
| --- | --- |
| Codex loses context across chats | Durable knowledge is committed into `wiki/` as Markdown pages, then reused through `search` and deeper `think` workflows. |
| AI writes too freely | Formal writes must go through `stage -> preview -> confirmation -> commit`, so Codex cannot silently write final knowledge into the vault. |
| The knowledge base gets messy | The vault has a fixed skeleton, OKF-style frontmatter, Router/Leaf page types, source references, tags, assets, and rebuildable indexes. |
| Duplicate or conflicting notes pile up | Write-time checks and maintenance workflows look for related notes, duplicate pages, conflicts, stale records, broken links, and orphan pages. |
| Screenshots and sources lose context | Assets and raw sources are stored in predictable folders and can be linked from formal knowledge pages. |
| Humans need to review what AI wrote | Obsidian is recommended as the review and navigation surface after commit, while Markdown and the glue script remain the source of truth. |

## Common Use Cases

You do not need to think in scripts or schemas during normal use. Talk to Codex in plain language and let the Skill handle the memory workflow.

### 1. Save project decisions

When a discussion ends with a decision, ask Codex to preserve it:

```text
Save this decision to my long-term memory and link it to the related project notes.
```

Useful for architecture choices, product direction, research conclusions, naming rules, workflow decisions, and tradeoffs you do not want to re-explain later.

### 2. Keep project rules consistent

When you correct Codex or establish a rule, turn it into durable memory:

```text
Remember this rule for future work: do not write business knowledge into the Skill folder; only write it into the Vault.
```

Useful for coding conventions, personal preferences, review standards, file organization rules, and repeatable operating principles.

### 3. Build a research memory base

When collecting sources, screenshots, links, or notes, ask Codex to organize them instead of leaving them in chat:

```text
Turn these research notes and links into a source note, then connect it to the relevant wiki pages.
```

Useful for product research, market research, paper reading, tool comparisons, legal or policy notes, and any workflow where sources matter.

### 4. Give screenshots and assets context

When an image, screenshot, PDF, or reference file matters, keep it connected to the knowledge it supports:

```text
Archive this screenshot as a memory asset and create a short note explaining what it proves.
```

Useful when visual evidence would otherwise sit in a random folder with no searchable explanation.

### 5. Ask Codex to answer with memory

Before making a recommendation, Codex can search or think with prior notes:

```text
Before answering, search my memory for related decisions and stale rules.
```

Useful when the answer depends on previous constraints, user preferences, past mistakes, or project-specific context.

### 6. Clean up the knowledge base

When the vault starts growing, ask Codex to inspect it:

```text
Audit my memory vault for duplicate notes, broken links, stale pages, and missing associations.
```

Useful for preventing the wiki from becoming another messy folder.

## What It Helps Codex Do

Use this Skill to ask Codex to:

- Save a conversation lesson, decision, rule, SOP, case, entity note, source note, screenshot, or asset.
- Create or update a structured OKF-style Markdown page inside a personal wiki.
- Stage AI-written memory first, preview it, and commit only after confirmation.
- Search existing memory before answering or writing new notes.
- Think with related memory when a question needs context, conflicts, stale-note checks, or synthesis.
- Process screenshots and other assets into predictable local folders.
- Build `categories.json` for fast lookup and `graph.json` for parent/link relationships.
- Audit the vault for duplicates, broken links, orphan pages, stale records, and missing metadata.
- Open committed notes in Obsidian for human review, browsing, and backlink inspection.

## Recommended Setup

Recommended:

```text
Codex + KW-OKF Memory Skill + local Markdown Vault + Obsidian
```

Obsidian gives you a comfortable human interface for reading, browsing links, searching, and reviewing committed notes. The Skill still treats Obsidian as a review surface, not the write authority.

Works without Obsidian:

```text
Codex + KW-OKF Memory Skill + local Markdown Vault
```

You can initialize, search, stage, commit, build, and audit the vault without installing Obsidian.

## How It Works

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
Audit + recommended Obsidian review
```

The key rule is simple: Codex can help write memory, but formal knowledge does not enter `wiki/` silently.

## Why It Is Different

- **Prevents messy AI-written knowledge bases**: Codex stages and previews before formal writes.
- **Preserves Codex memory across chats**: durable project knowledge survives beyond one conversation.
- **Karpathy-style wiki**: durable knowledge becomes small, readable, linkable pages.
- **Google OKF-inspired schema**: pages use typed frontmatter, parent routing, timestamps, sources, links, and evolution logs.
- **Obsidian-friendly**: recommended for review, navigation, search, and backlink inspection.
- **Markdown-first**: pages and assets are the source of truth, not generated JSON.
- **Audited**: formal writes go through staging, preview, confirmation, commit, build, and audit.
- **Agent-friendly**: structured frontmatter and indexes make it easier for Codex to locate the right memory quickly.
- **Bilingual-ready**: defaults to `en-US`, with `zh-CN` supported for Chinese workflows.

This is an independent project inspired by the wiki and OKF ideas above. It is not an official Google product or an official OKF compliance claim.

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

For the recommended Obsidian setup, open the generated `~/KnowledgeBase` folder as an Obsidian vault. If you want automatic post-commit opening, configure `obsidian_vault_name`, `obsidian_cli_path`, and `obsidian_auto_open_after_commit` in `skills/kw-okf-memory/config.json` after installation.

You can also pass `--vault <path>` to the glue script commands.

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
Open this committed note in Obsidian for review.
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

- It recommends Obsidian for review, but does not require it.
- It does not treat Obsidian as the write authority.
- It does not make generated JSON the source of truth.
- It does not silently create new top-level framework folders.
- It does not require a background daemon.
- It keeps formal wiki writes behind preview and confirmation.

## Status

This is an early public release for Codex users who want transparent, Obsidian-friendly, Markdown-based long-term memory. Feedback, issues, and improvements are welcome.
