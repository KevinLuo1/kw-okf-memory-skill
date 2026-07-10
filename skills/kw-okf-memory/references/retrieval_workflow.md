# Retrieval and Think Workflow

This workflow defines when to run only `search` and when to enter `think` mode. `think` is not a glue-layer command; it is Codex's working mode for running `search`, reading a small set of candidate note bodies, then synthesizing an answer with gaps, conflicts, and staleness risk.

## Mode Selection

Use `search` when the user wants to find, list, locate, or recall specific records.

Example signals, not exact trigger phrases:

- "find previous notes about xxx"
- "have we written about xxx"
- "list related pages"
- "which md contains this knowledge"
- "search xxx"

`search` matches path, `id`, parent path, title, summary, aliases, tags, scope, structural type, and business type. It returns `matched_fields` so Codex can explain why each candidate appeared. Do not rush into conclusions.

Use `think` when the user wants judgment, summary, comparison, decision support, planning, conflict checks, lesson extraction, or asks to combine prior memory.

Example signals, not exact trigger phrases:

- "based on long-term memory, should we change this"
- "does this plan have problems"
- "does this conflict with earlier decisions"
- "what should we do next"
- "what can we borrow from this"
- "decide where this note belongs and what it should link to"

`think` must run `search` first, use `graph.json` to inspect only relevant neighbors, then read the top 1-5 relevant note bodies. `graph.json` includes the root node, parent edges, resolved links, and dangling synapses. Do not scan the whole vault body text unless the user explicitly asks for a broad audit.

If the user explicitly says "only search" or "do not analyze", use only `search`. If the user explicitly asks to analyze with memory or make a judgment, use `think`. If unclear, search first and ask in one sentence whether synthesis is needed; when the task clearly needs advice, proceed with `think`.

## Think Output Format

A `think` answer must include:

- Conclusion: directly answer the user's current question.
- Evidence: list the memory pages or evidence used.
- Gaps: state what the Vault does not cover, what lacks evidence, or what needs user input.
- Staleness risk: state whether relevant pages may be outdated; treat `review_after` as a hard review signal, flag it when expired, and interpret `updated_at` together with whether the content depends on external reality instead of judging by age alone.
- Conflicts or uncertainty: call out contradictions, different boundaries, or uneven evidence strength between candidate pages.
- Recommendation: give the next action. If writing or modifying notes is needed, continue through `stage -> preview -> user confirmation -> commit`.

## Read/Write Boundary

`think` may read formal `wiki/` pages and system indexes, but it must not directly modify formal knowledge pages. Any change must be output as suggestions or staged drafts and wait for user confirmation.

Citations should use Vault-relative paths. When useful, mention the page title, `id`, `updated_at`, or `review_after` so the user can judge reliability.
