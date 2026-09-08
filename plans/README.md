# Translation refactor plan

Planned and implemented locally on 2026-09-06. The user authorized the refactor after reviewing the plan. Changes remain confined to `doc-builder`; live Jobs, Bucket writes, Transformers integration, and production activation have not been performed.

| Plan | Outcome | Priority | Effort | Depends on | Status |
| --- | --- | --- | --- | --- | --- |
| [001](001-simplify-translation.md) | Simplify translation within doc-builder, with a page cache, Hub-browsable translated files, and a completed archive for builds | P1 | L | None | DONE locally; live verification pending |

The parser, page cache, worker, Job runner, manual preview workflow, and opt-in shared consumer are implemented. The full repository suite passes (368 tests), and the parser checks pass across all 743 English pages at the pinned Transformers revision. Transformers workflow changes and production cutover are deferred, not completion requirements for this scope. Keep local implementation and later authorized live verification as separate status checkpoints.

The plan covers all 29 inline findings from mishig25's reviews, plus the dependency, glossary, MDX, corpus-CI, and live-build follow-ups in the review summaries. Its acceptance matrix distinguishes problems removed by the new architecture from checks that must still be implemented.

## Decisions

- Cache complete pages; accept retranslating a changed page to avoid segment storage and reconciliation.
- Translate prose units; preserve document structure and protected source content.
- Reuse the existing mdsvex parser through a small source-position adapter, subject to the explicit corpus gate.
- Use Transformers `generate_batch()` in an HF Job; retain the existing HTML build cache from PR #800.
- HF Jobs write only run-specific files. GitHub Actions owns updates to the shared translation cache and decides which completed archive to build.
- Keep translated Markdown/MDX as ordinary files under each completed run, with a Hub-readable README linking to them. The archive remains a build-transfer artifact, not the only way to inspect translations. Verify the requested Hub reading experience before claiming it works.
- Fail an update after one bounded retry if any required translation is unusable. Keep completed page translations cached and leave existing served docs alone.
- Do not add a publication pointer, source/output reconciliation manifest, background service, distributed lock, or inline artifact garbage collector.

## Alternatives not selected

- Segment-level blobs and an index: cheaper incremental inference, but reintroduces the state being removed.
- Updating a live translation directory: exposes partially written trees to readers.
- Concurrent remote writes to a canonical cache: unnecessary when remote Jobs can return a run-specific cache candidate.
- A new Markdown parser implemented with regexes: repeats the syntax failures in the review.
- Tree-sitter Markdown as the correctness authority: its own documentation warns against that use.
- A hard 750-line ceiling: encourages removing checks or hiding complexity. Count all new Python, JavaScript, and workflow code when reporting the actual reduction.
- Cross-repository workflow changes or production activation now: explicitly deferred by the user.
