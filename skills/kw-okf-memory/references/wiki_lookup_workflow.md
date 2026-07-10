# Wiki Lookup Workflow

Use the Vault as a human-readable wiki with machine-readable indexes. Prefer precise search, small reads, and link following over full-body scans.

## Lookup Flow

1. Search `categories.json` by title, aliases, tags, summary, `type`, `knowledge_type`, and scope.
2. Read only the 1-3 most relevant candidate notes when needed; if more candidates must be read to answer the current question or avoid missing key context, explain why and ask the user for permission first.
3. For ordinary precise lookup, use `categories.json` first to locate candidates; you may lightly check `graph.json` to see whether direct neighboring relationships exist, but only follow `graph.json`, candidate frontmatter `links`, and standard Markdown body links into note bodies when the question needs associated context, backlinks, upstream/downstream relationships, creative expansion, or `think`-style synthesis. Follow only the most relevant relationships in small amounts.
4. Treat dangling links as `dangling_synapse` warnings, not failures.

## Link Rules

- Use standard Markdown links: `[title](../relative/path.md)` or Vault-relative paths in frontmatter `links`.
- Do not use Obsidian private `[[WikiLinks]]` syntax.
- Do not create backlinks, merge notes, or rewrite relationships without preview and confirmation.

## Error Book

`error_book.yaml` records recurring knowledge-base issues or agent-behavior issues. By default, report `audit` issues without writing the error book automatically.

Common issue type examples: `duplicate_id`, `missing_parent`, `missing_parent_path`, `parent_id_mismatch`, `parent_path_mismatch`, `missing_image`, `dangling_synapse`, `expired_review`, `private_wikilink`, `illegal_type`, `illegal_link_path`, `illegal_body_link`, `illegal_review_after`.

Use `audit --write-error-book` only when the user explicitly wants the error book updated.
