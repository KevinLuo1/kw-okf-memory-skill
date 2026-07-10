# KW-OKF Memory Skill

[![CI](https://github.com/KevinLuo1/kw-okf-memory-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/KevinLuo1/kw-okf-memory-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Give Codex a structured Obsidian/Markdown memory wiki: Karpathy-style + an opinionated OKF-inspired KW-OKF profile, safe structure evolution, index-and-graph retrieval, staged AI writes, and optional OKF v0.1 export.

KW-OKF Memory is for people who use Codex across many chats and do not want their project knowledge scattered across old conversations. It is especially useful for long-running projects and long-lived knowledge bases where decisions, rules, research notes, screenshots, procedures, and lessons need to survive, stay organized, and remain reusable.

Recommended setup: **Codex + KW-OKF Memory + Obsidian + a local Markdown vault**. Obsidian is recommended for reading, browsing, backlinks, and review; the source of truth remains plain Markdown plus the audited glue workflow.

## Why Install It?

### 1. A long-term knowledge base that stays structured

This is not a random folder where AI drops Markdown files. The vault uses a Karpathy-style personal wiki plus an opinionated Google OKF-inspired profile: Router pages for categories, Leaf pages for concrete knowledge, frontmatter, `source_refs`, tags, assets, evolution logs, and a fixed vault skeleton.

The result: your knowledge base can keep growing without quickly becoming a pile of disconnected notes.

### 2. Structure can evolve, but AI cannot change it silently

The vault starts with a stable framework, but it is not frozen. Codex can propose new Routers, project folders, and associations when the current structure is not enough.

The important part: structural changes are previewed first and require confirmation. Codex can help the wiki evolve, but it cannot secretly reshape your vault.

### 3. Retrieval is index-based and association-aware

KW-OKF Memory rebuilds two JSON indexes from the Markdown source:

- `categories.json` tells Codex what knowledge exists, where it is, and what type it is.
- `graph.json` tells Codex how pages connect through parent structure and Markdown links.

The result: Codex does not have to blindly scan the whole vault. It can locate relevant notes, follow associations, read only the useful pages, and then reason with the connected context.

### 4. AI writes go through a safety gate

Formal wiki writes follow:

```text
stage -> preview -> confirmation -> commit -> build/audit
```

Codex can help capture and organize knowledge, but final `wiki/` pages are not written silently. You get a preview before durable memory changes land.

### 5. Strict internally, interoperable when needed

The internal Vault uses the stricter KW-OKF profile. It adds structural Router/Leaf types, path-derived ids, parent validation, confidence, source references, review dates, and staged writes. These are useful memory-system rules, but they mean the internal Vault does not claim direct OKF v0.1 conformance.

When another tool needs a portable bundle, `export-okf` creates a derived handoff with business-semantic concept types and reserved frontmatter-free `index.md` files. Your internal KW-OKF Vault remains unchanged.

## How You Use It

You do not need to think in scripts or schemas during normal use. Talk to Codex naturally.

```text
Save this decision to my long-term memory and link it to the related project notes.
```

```text
Before answering, search my memory for related decisions, old constraints, and stale rules.
```

```text
Archive this screenshot as a memory asset and create a short note explaining what it proves.
```

```text
Audit my memory vault for duplicate notes, broken links, stale pages, and missing associations.
```

A typical write looks like this:

1. You ask Codex to save or update knowledge.
2. Codex checks existing memory for related notes and possible duplicates.
3. Codex stages a draft in `inbox/staged/`.
4. You review the preview.
5. If assets are involved, Codex runs the previewed image operation with the confirmed directory/overwrite flags.
6. After confirmation, Codex commits the note into `wiki/`.
7. The Skill rebuilds `categories.json` and `graph.json`, then audits the changed pages.
8. You can review the committed note in Obsidian.

## What Problems It Solves

| Problem | How KW-OKF Memory solves it |
| --- | --- |
| Codex loses context across chats | Durable knowledge is committed into `wiki/` as Markdown pages and reused through `search` and deeper `think` workflows. |
| AI writes too freely | Formal writes must pass through `stage -> preview -> confirmation -> commit`, so Codex cannot silently write final knowledge. |
| The knowledge base gets messy | The vault uses a fixed skeleton, OKF-style frontmatter, Router/Leaf pages, source references, tags, assets, and rebuildable indexes. |
| Structure becomes too rigid | Codex may propose new Routers or folders, but structural changes require preview and confirmation. |
| Retrieval is inaccurate | `categories.json` supports targeted lookup, while `graph.json` supports association-aware reading and reasoning. |
| Duplicate or conflicting notes pile up | Write-time checks and maintenance workflows look for related notes, duplicates, conflicts, stale records, broken links, and orphan pages. |
| Screenshots and sources lose context | Assets and raw sources are stored in predictable folders and linked from formal knowledge pages. |
| Humans need to review what AI wrote | Obsidian is recommended as the review and navigation surface after commit, while Markdown and the glue script remain the source of truth. |

## Common Use Cases

### Save project decisions

Use it after architecture choices, product direction decisions, research conclusions, naming rules, workflow decisions, and tradeoffs you do not want to re-explain later.

```text
Save this decision to my long-term memory and link it to the related project notes.
```

### Keep project rules consistent

Use it when you correct Codex or establish a rule that should apply in future chats.

```text
Remember this rule for future work: do not write business knowledge into the Skill folder; only write it into the Vault.
```

### Build a research memory base

Use it when collecting sources, screenshots, links, or notes that should remain searchable and connected.

```text
Turn these research notes and links into a source note, then connect it to the relevant wiki pages.
```

### Give screenshots and assets context

Use it when visual evidence would otherwise sit in a random folder with no searchable explanation.

```text
Archive this screenshot as a memory asset and create a short note explaining what it proves.
```

### Ask Codex to answer with memory

Use it when the answer depends on previous constraints, preferences, mistakes, or project-specific context.

```text
Before answering, search my memory for related decisions and stale rules.
```

### Keep the knowledge base organized

Use it when the vault starts growing and needs maintenance.

```text
Audit my memory vault for duplicate notes, broken links, stale pages, and missing associations.
```

## Recommended Setup

```text
Codex + KW-OKF Memory Skill + local Markdown Vault + Obsidian
```

Obsidian gives you a comfortable human interface for reading, browsing links, searching, and reviewing committed notes. The Skill still treats Obsidian as a review surface, not the write authority.

Works without Obsidian:

```text
Codex + KW-OKF Memory Skill + local Markdown Vault
```

You can initialize, search, stage, commit, build, and audit the vault without installing Obsidian.

## Workflow

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

## Install In Codex

Requirements:

- Python 3.10 or newer.
- Pillow for `process-img`: `python -m pip install Pillow`.
- Obsidian is recommended but optional.

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

Preview and archive an image safely:

```bash
python scripts/okf_glue.py process-img --vault ~/KnowledgeBase --src ./source.png --dest assets/references/source.png --preview
python scripts/okf_glue.py process-img --vault ~/KnowledgeBase --src ./source.png --dest assets/references/source.png
```

If the preview lists new asset directories or an existing target, add `--allow-create-dirs` or `--overwrite` only after confirmation.

Preview and export an interoperable OKF-style handoff bundle:

```bash
python scripts/okf_glue.py export-okf --vault ~/KnowledgeBase --out ./knowledge-export --preview
python scripts/okf_glue.py export-okf --vault ~/KnowledgeBase --out ./knowledge-export
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
tests/                             # regression tests for write, audit, asset, and export boundaries
.github/workflows/ci.yml           # Python 3.10/3.13 continuous integration
```

Do not store personal vault content inside this repository. The Skill defines protocol and tools; your vault stores the knowledge.

## Safety Model

KW-OKF Memory is conservative by design:

- It recommends Obsidian for review, but does not require it.
- It does not treat Obsidian as the write authority.
- It does not make generated JSON the source of truth.
- It does not silently create new top-level framework folders.
- It does not silently create nested asset folders or overwrite assets.
- It does not require a background daemon.
- It keeps formal wiki writes behind preview and confirmation.
- It binds every staged draft to its previewed target and rolls back recoverable commit failures.

## Notes

This is an independent project inspired by [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and Google Cloud's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md). KW-OKF is an opinionated producer profile, not an official Google product and not a claim that the internal Vault directly conforms to OKF v0.1. Use `export-okf` for an interoperability-oriented handoff.

This is an early public release for Codex users who want transparent, Obsidian-friendly, Markdown-based long-term memory. Feedback, issues, and improvements are welcome.

## Development

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
