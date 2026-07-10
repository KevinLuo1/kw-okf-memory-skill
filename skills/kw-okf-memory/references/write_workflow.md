# Formal Write Workflow

Formal writing is the only path for turning candidate knowledge into committed Vault knowledge. It prioritizes search first, preview first, then user confirmation to prevent duplicate pages, wrong directories, and silent writes.

## When To Use

Enter this workflow for explicit preservation or write intent: the user wants Codex to save knowledge, preserve a lesson, distill a rule/SOP/case/decision, create or update an OKF page, update long-term memory, or archive an image/product lesson as knowledge.

Do not treat ordinary lookup, judgment, or synthesis as permission to write. Lookup and synthesis use `retrieval_workflow.md`; deep cleanup uses `maintenance_workflow.md`.

## Pre-Write Triage

1. Read `config.json` to locate the Vault, default language, supported languages, Obsidian settings, and directory confirmation rules.
2. Decide body language: explicit user choice wins; otherwise follow the current conversation language; if unclear, use the configured fallback language. This public release defaults to `en-US` and also supports `zh-CN`.
3. Decide the target kind: new Router, normal `LEAF_RULE`, existing-page update, or image-asset-only processing; also decide whether missing Routers or business directories need to be created.
4. Read `okf_schema.md` to confirm fields and body structure.
5. Read `vault_framework.md` to confirm the target path is allowed.
6. If root `tags.md` exists, read the tag registry first; prefer existing tags, and give every new tag a meaning and applicability boundary.
7. Search `categories.json` or use `search` for lightweight locating; if the index is missing or clearly stale, run `build` first, and do not default to full-vault body scans.
8. Run lightweight association checks using title, summary, tags, `knowledge_type`, parent Router, and body keywords.
9. If needed, read only the top 1-3 relevant candidate note bodies; if more candidates must be read to avoid duplicates, wrong links, or missed key conflicts, explain why and ask the user for permission first.
10. If a likely duplicate appears, discuss merge, existing-page update, or explicit target overwrite first; overwrites require separate preview and user confirmation, and do not create duplicate pages directly.

## Stage Draft

Generate drafts with the glue script:

```bash
python scripts/okf_glue.py stage --type LEAF_RULE --parent-id <id> --parent-path <path> --knowledge-type <type> --title <title> --summary <summary> --target <wiki/path.md>
```

Write rules:

- `--target` must be `wiki/**/*.md`.
- `ROUTER` and `LEAF_RULE` require `parent_id` and `parent_path`.
- `LEAF_RULE` requires `knowledge_type`.
- Pass `--language en-US|zh-CN` when the user chooses a supported language.
- Put evidence in `--source-ref`, assets in `--image`, and high-confidence links in `--link`.
- Planned business directories must appear in `planned_directory_creates`.
- Planned missing Routers must appear in `planned_router_creates` and inherit the current draft language.

## Preview Requirements

Before asking for confirmation, show the user:

- target path, parent node, structural type, business type, and body language
- chosen tags, reused `tags.md` entries, and any new tags with meaning and applicability boundary
- the draft body or a sufficiently complete body preview
- sources, images, and default-write links
- suggested links, possible duplicates, do-not-link candidates, and the reason for each candidate
- planned directory or Router creation
- low confidence, weak evidence, dangling links, possible conflicts, or other risks

User confirmation of the full preview counts as confirmation for links, directories, and Routers marked as default-write. The user may change the title, path, links, or cancel before commit.

## Batch Confirmation

The user may grant batch confirmation in natural language for one clearly scoped ordinary write or cleanup task, such as "organize this Router now; do not ask me for every individual change." Before acting, restate the batch scope, allowed actions, and excluded actions.

After batch confirmation, ordinary creates, supplements, link additions, tag updates, previewed runtime business directories, or missing Routers already listed in the preview may proceed to `commit` without repeated per-file questions.

Batch confirmation does not cover new top-level directories, new `wiki/` first-level categories, schema changes, framework-reference changes, formal-knowledge deletion, large merges, overwriting existing target pages, or any new risk outside the preview. Pause and ask for separate confirmation in those cases.

## Commit Rules

Commit only after explicit user confirmation. A single-note preview confirmation or a valid batch confirmation defined in this workflow counts as explicit confirmation:

```bash
python scripts/okf_glue.py commit --draft <draft.md> --target <wiki/path.md>
```

Use extra flags only after the corresponding risk was previewed and confirmed:

- `--allow-create-dirs`: create the business directories listed in the preview.
- `--allow-create-router`: create the missing Router listed in the preview.
- `--overwrite`: replace an existing target page; this requires explicit user confirmation.

After `commit`, refresh or inspect `build` / `audit` results. If the preview confirmed new or changed tag-registry entries, maintain root `tags.md` as an explicit human/AI step; there is currently no dedicated script for this, so do not silently rewrite it. If Obsidian integration is configured, treat it as a human review surface only.

## Updating Existing Knowledge

Updating existing pages is riskier than creating new pages:

- Say whether the change replaces, supplements, splits, or deprecates prior knowledge.
- Preserve traceable sources and the evolution log.
- Record replacement through `supersedes` / `superseded_by` or in the body where appropriate.
- If replacement is uncertain, produce suggestions or a staged draft instead of overwriting.

## Stop Conditions

Stop and explain when:

- the target path is not valid `wiki/**/*.md`
- the write requires a new top-level directory or new `wiki/` first-level category
- the parent node is missing and the user has not confirmed Router creation
- a likely duplicate appears and merge-vs-new is unclear
- evidence is too weak to support the page conclusion
- the user asks to skip preview or silently write a formal page
