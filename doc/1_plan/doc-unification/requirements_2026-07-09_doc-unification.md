# Requirement: unify document tree under doc
> Date: 2026-07-09
> Status: trial
> Entry: User reported that BridgeForge had both a canonical `doc/` tree and a legacy `docs` tree, and asked to standardize on `doc/` while整理 existing legacy content into `doc/`.

## Background And Goal

BridgeForge had two top-level documentation trees:

- `doc/`: the current BridgeForge document system used by feature-dev, archive-scan, todo, find-doc, and the template workflow rules.
- `docs`: older meta documentation, investigation reports, playbooks, handoffs, debates, and reference examples.

The goal is to make `doc/` the only top-level document system, move existing legacy content into the appropriate `doc/` layers, and update live references so users and automation do not keep pointing at the old path.

## Non-Goals

- Do not delete historical documents.
- Do not rewrite document meaning beyond path and index adjustments.
- Do not change the six-layer `doc/` structure.
- Do not commit or push changes.

## User-Visible Behavior

- The legacy root `docs` tree no longer exists after migration.
- All BridgeForge documentation lives under `doc/`.
- Links in root docs, rules, skills, scripts, templates, and changelog entries point to the new `doc/` locations.
- `doc/README.md` is the single index for the migrated documents.

## Constraints And Risk Boundaries

- Product-layer references under `templates/` and `skills/` must be updated because they can be copied to downstream projects.
- Generated report paths, especially the Codex harness parity report, must be updated in both scripts and text references.
- Historical changelog entries may retain old wording only if they are clearly historical, but live links should point to current files.
- The migration should preserve content and allow Git to detect renames from the moved files.

## Acceptance Checklist

- [x] The legacy root `docs` tree is gone.
- [x] `doc/README.md` indexes the moved documents.
- [x] Live references to the old tree are updated to `doc/...`.
- [x] Harness parity generation targets `doc/3_design/codex-harness-parity.md`.
- [x] Repo search shows no unintended old-tree path references.
- [x] Relevant automated checks pass or any gaps are explicitly recorded.

## Deferred Items

- No deferred items identified at start.

## Implementation Plan

1. Move legacy documents into `doc/3_design/`, `doc/4_archive/`, and `doc/9_reference/`.
2. Update references in root docs, templates, skills, scripts, and tests.
3. Update `doc/README.md` as the unique index.
4. Update version/changelog metadata for product-layer path references.
5. Run path searches and relevant harness checks.

## Implementation Record

- 2026-07-09: Requirement confirmed by user. Migration started.
- 2026-07-09: Legacy documents moved into `doc/3_design/`, `doc/4_archive/`, and `doc/9_reference/`; root `docs` tree removed.
- 2026-07-09: Live references, generated report targets, version files, and changelogs updated.
- 2026-07-09: Independent review found stale dogfood references and stale example paths; both were fixed.

## Verification Record

- `Test-Path docs` returned `False`.
- Old-tree path search returned no matches for legacy path patterns or stale example paths.
- `python .codex/scripts/harness_parity_check.py --check` exited 0.
- `python tests/harness/run_downstream_fixture.py` exited 0 with all listed checks passing.
- `python .codex/hooks/encoding_check.py` exited 0.
- `git -c safe.directory=D:/Quant/BridgeForge diff --check` exited 0.
- Independent review agent initially found stale dogfood references and stale example paths; follow-up search exited with no matches after fixes.

## User Trial Feedback

- Pending.
