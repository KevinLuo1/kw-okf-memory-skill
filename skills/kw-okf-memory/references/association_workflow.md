# Association Workflow

Association is routed by task intent: lightweight association during normal writes, and explicit deep association cleanup when the user intends to inspect or reorganize relationships.

## Lightweight Association On Write

During each new memory write:

1. Search `categories.json` with title, summary, tags, `knowledge_type`, parent Router, and key body phrases.
2. If needed, read only the top 1-3 candidate note bodies; if more candidates must be read to avoid duplicates, wrong links, or missed key conflicts, explain why and ask the user for permission first.
3. Present candidates grouped as `Suggested Links`, `Possible Duplicates`, and `Do Not Link` using the user's current language in the chat.
4. Explain the relationship reason for each candidate.
5. Default-write only high-confidence links that are shown in the preview.
6. Show low-confidence candidates without writing them unless the user confirms.
7. If a candidate is a likely duplicate, prefer merge/overwrite discussion over creating a duplicate page.

User confirmation of the full preview counts as confirmation for links marked as default-write. The user may add or remove links before commit.

## Relationship Type Labels

This workflow does not add a complex schema. Frontmatter `links` still stores only Vault-relative paths; relationship types are written in the body `Related Knowledge` section, maintenance reports, or staged previews.

Recommended relationship types:

| Type | Meaning |
| --- | --- |
| `related_to` | Same topic, adjacent background, or useful cross-reference. |
| `supports` | The linked page provides evidence or a case for the current conclusion. |
| `depends_on` | The current rule depends on the linked page's prerequisite rule, background, or constraint. |
| `conflicts_with` | The pages may conflict and need applicability boundaries. |
| `supersedes` | The current page replaces an older page; formal replacements should also update frontmatter `supersedes`. |
| `superseded_by` | The current page has been replaced by a newer page; formal replacements should also update frontmatter `superseded_by`. |
| `mentions` | The page only mentions a related entity or concept; it is not a strong dependency. |
| `example_of` | The current page is a case, example, sample, or retrospective for the linked rule, procedure, decision, or concept. |
| `implements` | The current page is an execution plan, operating procedure, or tool implementation for the linked rule, decision, or principle. |
| `evidence_for` | The current page provides evidence for the linked page. |

Body example:

```markdown
## Related Knowledge
- `supports`: [Bilingual Skill/Vault Boundary](../projects/kw-okf-memory/bilingual-skill-vault-boundary.md) provides evidence for the Skill/Vault separation decision.
- `depends_on`: [OKF Schema](../procedures/okf-schema.md) defines the frontmatter field boundary.
- `related_to`: [Retrieval and Think Workflow](retrieval_workflow.md) is part of the long-term memory read path.
```

Rules: every relationship type needs a one-sentence reason; low-confidence relationships are shown only as suggestions and are not default-written; do not overuse generic `related_to` when `supports`, `depends_on`, `conflicts_with`, `example_of`, or `implements` fits better.

## Deep Association Cleanup

Run only for an explicit deep-association intent, such as organizing associations, auditing relationships, finding orphan/duplicate/conflicting pages, or checking the knowledge graph under a Router.

Deep cleanup may inspect a wider scope and suggest orphan notes, duplicate notes, conflicting rules, missing parent/child relationships, missing links or backlinks, and merge candidates.

Deep cleanup still cannot write formal changes directly. It must output suggestions or staged drafts, then follow preview -> user confirmation -> commit.
