# SDD ledger — plan: docs/superpowers/plans/2026-08-11-pragmatic-v2-live-simulator.md

Preflight: complete
- Preserved superseded Task 7 artifacts in `stash@{0}` named `superseded-v2-task7-before-pragmatic-live-loop`; exact eight-path inventory verified.
- Existing linked worktree confirmed on `codex/v2-live-simulator`.
- Baseline: `1555 passed, 43 skipped, 15 known warnings`.
- Plan commits: `2512197` plus preflight corrections `c3acf80`; independent preflight found no unresolved execution blocker after correction.
- Task 1 feasibility: use one-session aggregate/runtime + Task 5 mapper load, bootstrap only timed/capacity visits, and transition zero-touch steps without fabricated samples.

Task 1: fix round 1/5 (2 addressed, 0 open — fixed-boundary timing and below-minimum scope selection; commit `93b9a72`).
Task 1: minor (deferred): bootstrap requests the same deterministic touch draw twice instead of threading the retained draw object.
Task 1: complete (commits `c3acf80..93b9a72`, review clean).

Task 2: implementation commit `cf520c2`; review found three Important issues (availability composition, early-completion time loss, and non-causal ground truth).
Task 2: fix round 1/5 (2 addressed, 1 open — segment-local queue cause still inferred from final instant; commit `f22e7d4`).
Task 2: fix round 2/5 (0 addressed, 1 open — cause retained at the right segment but partial limits can still be mislabeled; commit `5a170ee`).
Task 2: fix round 3/5 (1 addressed, 0 open — allocation emits actual queue constraint; commit `1dd6e45`).
Task 2: minor (deferred): exact-type guards exceed the pragmatic input-hardening bar.
Task 2: minor (deferred): the tick module combines allocation, transition, and evidence presentation in one large module.
Task 2: complete (commits `93b9a72..1dd6e45`, review clean).

Task 3: implementation commit `d73f8e0`; review found two Important issues (due-team starvation after the first 100 and restart boundary committed before downtime evidence).
Task 3: fix round 1/5 (2 addressed, 0 open; commit `0973236`).
Task 3: complete (commits `1dd6e45..0973236`, review clean).

Task 4: implementation commit `d3d2d49`; review found two Important issues (missing scope IDs falsely delivered and sprint marker preflight only scanned the first Jira page).
Task 4: fix round 1/5 (2 addressed, 0 open; commit `bd7430a`).
Task 4: complete (commits `0973236..bd7430a`, review clean).

Task 5: implementation commits `75b0f42`, `11ded36`; review found five Important issues (test-only provisioning, missing negative-decision ground truth, repeated dependency decisions, wall-clock long-stay timing, and conflicting simultaneous risk outcomes).
Task 5: minor (deferred): the initial risk module has several handlers over 30 lines and combines all policy/evidence plumbing in one large module; address opportunistically during correctness refactor and send any residual to final review.
Task 5: fix round 1/5 (5 addressed, 1 open — dependency continuation changed pause/queue state without causal delta ground truth; commits `e736bb9`, `0092aae`).
Task 5: fix round 2/5 (1 addressed, 0 open — continuation evidence now records each committed wait delta without redraw/activity/projection; commits `dbeec09`, `6a27c06`).
Task 5: complete (commits `bd7430a..6a27c06`, review clean).

Final review: NOT CLEAN — two Critical issues (risk effects beyond committed cursor; late bootstrap can rewind runtime) and two Important issues (active bootstrap sprint lacks Jira provisioning; intrinsic pause mistaken for dependency continuation). One consolidated fix wave authorized by the SDD workflow.
Final review correction: COMPLETE — all four findings closed in implementation commit `5ca529bf3fba78b113642d0181bf038b877991ee`; focused `27 passed`, affected `78 passed`, all-v2 `1119 passed` with one baseline warning, Ruff clean, sole Alembic head 016, no migration, and independent final review found no Critical or Important issue.
