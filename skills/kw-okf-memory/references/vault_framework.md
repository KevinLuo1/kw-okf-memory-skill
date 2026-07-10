# Vault Framework

The Vault is the truth source for long-term memory. The Skill folder stores tools and protocol only.

The internal Vault follows the stricter KW-OKF profile. It is OKF-inspired rather than directly OKF v0.1 conformant because Router `index.md` files carry KW-OKF frontmatter. Use `export-okf` for an interoperable derived bundle; never treat the export as the internal truth source.

## Fixed Skeleton

The fixed skeleton contains the following root files and directories:

```text
index.md
log.md
categories.json
graph.json
error_book.yaml
tags.md
inbox/
inbox/raw_chats/
inbox/raw_sources/
inbox/staged/
inbox/staged/committed/
assets/
assets/images/
assets/products/
assets/screenshots/
assets/documents/
assets/references/
wiki/
wiki/projects/
wiki/domains/
wiki/entities/
wiki/decisions/
wiki/procedures/
wiki/cases/
wiki/sources/
```

## Skeleton Roles

| Path | Purpose |
| --- | --- |
| `index.md` | Global Vault entry index, rebuilt by `build` from `wiki/`; do not hand-write business knowledge here. |
| `log.md` | Global change audit log for operations such as `init`, `build`, and `commit`. |
| `categories.json` | Rebuildable category and node index from formal `wiki/` pages; used by `search` and lightweight locating. |
| `graph.json` | Rebuildable graph from parent links and Markdown links; used for association, orphan, and dangling-link checks. |
| `error_book.yaml` | Recurring knowledge-base or agent-behavior issues; update only when explicitly needed. |
| `tags.md` | Global tag registry for tag meaning, applicability, aliases/discouraged spellings, and status. |
| `inbox/` | Root for temporary inputs, drafts, and unprocessed material; not formal knowledge. |
| `inbox/raw_chats/` | Raw conversation excerpts and chat fragments waiting for distillation. |
| `inbox/raw_sources/` | Raw source material, external references, and manual notes. |
| `inbox/staged/` | Staged drafts waiting for preview and user confirmation. |
| `inbox/staged/committed/` | Archive of committed drafts for write-path traceability. |
| `assets/` | Root for non-Markdown assets such as images and documents. |
| `assets/images/` | General image assets. |
| `assets/products/` | Product images and product-related media. |
| `assets/screenshots/` | Screenshot assets. |
| `assets/documents/` | Documents, PDFs, attachments, and similar files. |
| `assets/references/` | Reference images, evidence images, and source-support material. |
| `wiki/` | Formal knowledge root; `build` and `audit` scan formal Markdown knowledge pages here. |
| `wiki/projects/` | Project knowledge, project-local rules, and project context. |
| `wiki/domains/` | Cross-project domain knowledge, general principles, and methods. |
| `wiki/entities/` | People, organizations, tools, products, objects, and other entities. |
| `wiki/decisions/` | Decision records and tradeoff rationale. |
| `wiki/procedures/` | SOPs, workflows, and operating procedures. |
| `wiki/cases/` | Cases, incidents, retrospectives, and concrete lessons. |
| `wiki/sources/` | Source descriptions, source indexes, and evidence records. |

Root system files are reserved. Ordinary `stage --target` and `commit --target` must point to `wiki/**/*.md`, not Vault root files. `tags.md` is the global tag registry: it records used or approved reusable tags, meanings, applicability boundaries, aliases/discouraged spellings, and status. It is the human/AI-maintained truth source for tag meanings and is not rebuilt from note bodies by `build`. `categories.json` reflects actual page tags and index data; it does not replace `tags.md`.

## Directory Rules

AI may suggest runtime business subdirectories under the fixed skeleton. Business subdirectories and note filenames are human-readable semantic names chosen by Codex from the current task context; they may be English, Chinese, or mixed. Prefer portable English slugs for public repositories, for example `wiki/projects/kw-okf-memory/`, `wiki/projects/ozon-weight-plugin/cases/`, `wiki/domains/software-engineering/debugging/`, or `assets/products/heated-plush-toys/`.

AI may not silently create runtime business directories. `stage` must list `planned_directory_creates`; `commit` may create them only with `--allow-create-dirs` after user confirmation.

The same rule applies to nested asset directories. Run `process-img --preview` first; actual creation requires `--allow-create-dirs`. Existing assets are never silently replaced and require `--overwrite` after preview and explicit confirmation.

Ordinary writes must not add new top-level directories or new first-level `wiki/` categories such as `wiki/abc/`. Even if the user has granted batch confirmation for a cleanup task, this kind of addition remains a framework change: separately explain why it is needed, what the directory means, and its impact, then get explicit user confirmation and update this reference or the spec before creating it.

## Path Safety

Reject relative targets containing absolute paths, drive letters, UNC prefixes, empty segments, `.`, `..`, control characters, or wildcard characters.

Allowed formal note targets: `wiki/**/*.md`. Path arguments may be raw Unicode or UTF-8 percent-encoded ASCII; prefer portable ASCII slugs for public repositories.

Allowed image destinations: `assets/products/*`, `assets/screenshots/*`, `assets/references/*`, `assets/images/*`; supported extensions are `.jpg`, `.jpeg`, `.png`, and `.webp`, and `process-img` saves according to the destination extension.

`process-img` expands square images to the configured target ratio without cropping. Non-square images keep their original ratio unless `--force-ratio` was previewed and confirmed; forced conversion expands the canvas and does not crop the subject.

`export-okf --out <path>` writes outside the internal Vault by default. Use `--preview` before export and `--overwrite` only for a previously reviewed destination carrying the `.kw-okf-export.json` marker; the command refuses to delete non-empty unmanaged directories. It exports `LEAF_RULE` pages as business-typed concepts, copies referenced assets, and generates frontmatter-free reserved index files.

`build` and `audit` scan formal knowledge only under `wiki/`; `inbox/` drafts, archived committed drafts under `inbox/staged/committed/`, and `assets/` files are not formal knowledge pages.
