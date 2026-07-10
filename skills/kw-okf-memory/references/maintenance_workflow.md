# Maintenance Workflow

Maintenance is a user-triggered lightweight cleanup loop. It does not run background jobs or periodically modify the Vault automatically. Use it to check vault health, duplicates, conflicts, stale notes, and missing associations.

## When To Run

Run this workflow when the user explicitly asks for cleanup, review, or knowledge-base health checks. If normal writing, retrieval, or `audit` reveals clear duplicates, conflicts, stale notes, orphan pages, missing associations, or tag drift, AI may recommend this workflow, but must not perform formal modifications automatically.

Typical triggers include organizing the knowledge base, inspecting duplicates/conflicts/stale notes, reviewing a Router subgraph, finding orphan pages, adding missing links/backlinks, or performing maintenance/review/deep cleanup.

Normal writes do not enter the full maintenance workflow. They only run lightweight write-time association.

## Command Roles

| Command | Purpose | When to use |
| --- | --- | --- |
| `init` | Create the fixed Vault skeleton and minimal system files | Use only for a new Vault or missing skeleton; it is not a routine maintenance command. |
| `build` | Rebuild `index.md`, `categories.json`, and `graph.json` from `wiki/` | Run at the start of maintenance so indexes reflect current Markdown; run again after committed fixes. |
| `audit` | Check schema, path-derived ids, path shape, parent consistency, field types, timestamps, images, source refs, frontmatter/body links, body structure, duplicate ids, expired reviews, and private WikiLinks | Main maintenance entry point; by default it only reports issues, and updates `error_book.yaml` only when `--write-error-book` is explicitly used. |
| `search` | Query path, id, parent path, title, summary, aliases, tags, type, and scope in `categories.json`; automatically rebuild a missing or older index | Use `matched_fields` to locate likely duplicates, nearby topics, and similar rules; do not treat it as the final answer by itself. |
| `stage` | Create a draft under `inbox/staged/` and show planned directory or Router creation | Use when a maintenance suggestion needs an actual page change; it creates drafts only. |
| `commit` | After user confirmation, write a staged draft to formal `wiki/`, archive the draft, rebuild indexes, and append logs | Use only after per-item user confirmation or scoped batch confirmation. |
| `process-img` | Preview and archive image assets under `assets/` with explicit directory/overwrite gates | Use when maintaining image references, product images, screenshots, or reference images. |
| `obsidian-open` | Open a target Vault page | Use for human review only; Obsidian is not the write authority. |
| `obsidian-search` | Open a search in Obsidian | Use for human context and backlink review; it does not replace `build` / `audit`. |

## Standard Flow

1. Define scope: whole Vault, first-level category, Router, or issue type.
2. Run `build` to refresh global indexes and graph.
3. Run `audit`; classify findings as errors, warnings, and suggestions; analyze errors first, then warnings.
4. Use `search`, `categories.json`, `graph.json`, and `tags.md` to preliminarily screen likely duplicates, orphans, missing associations, stale notes, tag drift, and conflicts.
5. When needed, read only a small number of the most relevant note bodies, then output a maintenance report; do not directly modify formal pages.
6. If changes are needed, generate staged drafts and show the staged preview, reason, and impact for each change.
7. Commit only after per-item user confirmation or scoped batch confirmation.
8. After commit, run or review `build` and `audit` again.

## Batch Cleanup Confirmation

The user may grant batch confirmation for one clearly scoped maintenance task. First output the maintenance scope, allowed actions, excluded actions, and risk boundary; after the user confirms, ordinary fixes listed in the maintenance report and shown in staged previews may be committed in batch.

Batch confirmation only covers ordinary maintenance actions such as adding links, adding tag explanations, updating sources, marking stale notes, and creating previewed runtime business directories or missing Routers. It does not cover new top-level directories, new `wiki/` first-level categories, schema or framework changes, formal-knowledge deletion, overwriting existing pages, large merges, or new risks found outside the preview.

## Checks

These are maintenance-check dimensions, not standalone commands. Codex should select the relevant checks for the current maintenance scope, prefer `build`, `audit`, `search`, `categories.json`, `graph.json`, and `tags.md` to narrow the scope first, then read only a small amount of note body text to confirm.

- Orphan pages: formal notes with no useful associations beyond the parent tree, or no inbound references from other pages.
- Likely duplicates: pages with highly similar title, summary, tags, `knowledge_type`, and `scope`; semantic duplicates are only suspected until user-confirmed.
- Conflicts: rules, decisions, or SOPs in the same scope that disagree; list evidence and applicability boundaries.
- Stale notes: `review_after` has passed, or `updated_at` is old and the content depends on external reality.
- Missing associations: the body mentions related knowledge without standard Markdown links, or frontmatter `links` and the body `Related Knowledge` section diverge.
- Parent structure issues: `parent_id`, `parent_path`, directory hierarchy, structural path shape, and Router semantics disagree.
- Tag registry problems: page `tags` lack explanations in `tags.md`, synonym tags duplicate each other, deprecated tags are still used, or tag meanings do not match page content.

## Maintenance Report Format

A maintenance report should include:

- Scope: directories, Routers, or issue types inspected.
- Conclusion: whether the knowledge base is healthy and what must be handled.
- Findings: grouped by error, warning, and suggestion, with page, evidence, and reason.
- Proposed changes: link additions, merges, splits, stale marks, source updates, new pages, or tag additions/merges/deprecations.
- Deferred items: low-confidence or evidence-light items that need user judgment.
- Next action: if changes are needed, continue through `stage -> preview -> user confirmation/batch confirmation -> commit`.

## Write Boundary

Maintenance must not silently modify formal `wiki/` pages. Any fix must first be output as suggestions or staged drafts and wait for user confirmation; valid batch confirmation only replaces repeated per-item confirmation, not preview or risk explanation.

Maintenance may read a wider scope, but it should still use indexes and graphs first to narrow the work. Read broad body text only when the user asks for a full audit.
