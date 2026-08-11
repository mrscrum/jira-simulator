# Agent Instruction — Jira Team Simulator

## Current Stage and Baseline

Stage labels in `backlog/` are not a reliable description of the code. The repository contains
configuration UI, Jira integration, a distribution-based simulation rewrite, precomputed sprint
schedules, and scheduled-event dispatch. The north-star end-to-end workflow is still partial and
has not been verified against the live `mrscrum` Jira instance in the latest assessment.

Read `docs/requirements-functionality-map.md` before planning implementation. It is the
evidence-backed baseline as of 2026-08-10 (`main` at `b65b133`).

The approved additive v2 specification and execution plan now begin at `docs/v2/README.md` and are
tracked under `backlog/v2/`. Historical Stage 4/5 plans are not executable for v2.

## Product Boundary

- Connect exactly one Jira instance: `mrscrum`.
- Use one global Jira credential set and Jira client.
- Support multiple teams; each team maps to a distinct Jira project and is configured separately.
- Keep all Jira writes behind the persistent write queue.
- Never use a simulator-originated update to change Jira's actual assignee or reporter after issue
  creation. Preserve direct human changes; use virtual ownership fields and internal state.
- Simulation timing is statistical and Jira statuses map 1:1 to configured workflow statuses.

## What Is Implemented

- FastAPI backend with 76 OpenAPI operations and 32 SQLAlchemy tables.
- React UI for teams, members, workflows, timing templates, move-left configuration,
  dependencies, simulation controls, and sprint/event schedules.
- Per-team project key/board, members, workflow, timing, sprint, calendar, and backlog settings.
- Log-normal full-time and uniform work-time distributions.
- Sprint planning, move-left rolls, working-calendar calculations, and deterministic precompute.
- Persistent scheduled events, Jira write queue, rate-limit handling, Jira client, bootstrapper,
  health monitor, and queue-status auditor.
- Terraform, Docker Compose, Nginx, and GitHub Actions deployment assets.

## Most Recent Change

On 2026-08-10, M1 Task 2 review fix round 2 made the live-slice JSON boundary strict about object
keys. `DraftEnvelope` and all three draft factories now reject integer, boolean, `None`, mixed, and
nested non-string mapping keys before canonical encoding or session creation, preventing silent
`json.dumps` coercion. Valid strict JSON retains the same canonical bytes/hash and deep immutability.

On 2026-08-10, M1 Task 2 review fix round 1 hardened revision-014 contracts without changing its
schema. Direct construction, `dataclasses.replace`, and the UOW boundary now revalidate semantic
UUIDs, canonical JSON/digests, non-empty type fields, non-negative versions, pending status, and
aware instants before opening a session. Semantic-key insert races recover through a savepoint:
identical content resolves to the winner, while differing content raises the typed conflict and
rolls back the runtime plus all ledgers. Deep payload aliases reject `|=` and nested mutation. Every
fresh public v2 model/UOW import order registers all seven v2 tables and can create the SQLite
schema. Adapter-failure coverage now reloads ground truth explicitly as well as runtime, activity,
and projection state.

M1 Task 2 originally added revision 014 above the reviewed revision-013 team shell. Runtime rows
expose an explicit optimistic version, and `backend/app/v2/persistence/unit_of_work.py` uses one
compare-and-swap plus one database transaction to advance runtime and append ordered activity,
immutable ground truth, and generic pending projection intent. Deterministic semantic UUIDs,
canonical payload hashes, stable append cursors, stale-writer rollback, disposed-engine restart,
and post-commit adapter failure are covered by focused tests.
`backend/alembic/versions/014_add_v2_live_slice_ledgers.py` backfills version zero without retaining
a server default, owns all three new tables, and returns exactly to populated revision 013 on
downgrade. V2 remains isolated from the legacy runtime and invokes no Jira/OpenAI adapter.

On 2026-08-10, Pavel approved the v2 product direction and then asked to keep the plan high level,
leaving implementation detail to the capable model that builds it. The active requirements,
architecture, roadmap, and MVP outcome now live in `docs/v2/high-level-plan.md`; milestone status is
in `backlog/v2/README.md`. Earlier detailed v2 contracts and the 96-task decomposition are retained
only as optional design exploration. Pavel additionally required managed projects to survive direct
Jira sprint/card intervention, which remains an explicit active requirement. No source-code fixes or
runtime changes were made.

Local evidence:

- Backend: 699 passed, 43 skipped, 15 baseline warnings.
- Ruff: passed.
- Frontend: 2 tests passed.
- Frontend production build: passed with a bundle-size warning.
- Real Jira integration tests were not run and remain skipped in normal CI.

## Key Files

- `AGENTS.md` — mandatory development flow and highest-priority repository rules.
- `docs/requirements-functionality-map.md` — current requirements/functionality baseline.
- `docs/v2/high-level-plan.md` — active v2 requirements, architecture, roadmap, and MVP acceptance.
- `docs/v2/implementation-prompt.md` — ready-to-paste mandate for a long independent implementation
  run, including autonomy, safety, priorities, verification, and morning handoff.
- `docs/v2/README.md` — authority and resumption instructions.
- `backlog/v2/README.md` — active milestone status.
- Other files under `docs/v2/` and `backlog/v2/stage-*.md` — optional detailed planning reference,
  not the active contract or mandatory task sequence.
- `docs/simulation-engine-rewrite-requirements.md` — superseded v1 requirements; historical only.
- `backend/app/main.py` — application/service/scheduler wiring.
- `backend/app/engine/simulation.py` — lifecycle tick and sprint precompute persistence.
- `backend/app/engine/precompute.py` — in-memory sprint simulation and event generation.
- `backend/app/engine/workflow_engine.py` — per-item distribution/capacity/status logic.
- `backend/app/engine/event_dispatcher.py` — moves due scheduled events to the Jira queue.
- `backend/app/integrations/jira_write_queue.py` — external-write boundary and operation routing.
- `backend/app/integrations/jira_client.py` — Jira REST/Agile API client.
- `backend/app/integrations/scheduler.py` — background jobs and paused startup behavior.
- `backend/app/api/routers/scheduled_events.py` — sprint/schedule management and diagnostics.
- `backend/app/v2/domain/live_slice.py` — immutable live-slice drafts, stored records, runtime
  advance, transaction command/result, and page contracts.
- `backend/app/v2/persistence/unit_of_work.py` — the v2 persistence port and atomic SQLAlchemy
  compare-and-swap implementation; it must not import or call an external adapter.
- `backend/app/v2/persistence/live_models.py` — the three append-oriented ledger mappings.
- `backend/alembic/versions/014_add_v2_live_slice_ledgers.py` — reversible runtime-version and
  live-ledger migration above revision 013.
- `frontend/src/App.tsx` — top-level UI section routing.
- `docker-compose.yml` — current PostgreSQL deployment, conflicting with SQLite-on-EBS rules.

## Next Task

The active near-term M1 persistence plan has no further approved implementation slice after Task 2.
Keep M1 in progress, review the Task 1/Task 2 evidence, and define the next context-sized M1 slice
from the high-level plan before writing more code. Any live Jira provisioning test still requires a
Pavel-authorized disposable project/tenant.

## Active Decisions and External Gates

1. Build an additive persisted-live v2 modular monolith, initially using SQLite/WAL on EBS and one
   scheduler owner.
2. Deliver Scrum and Codex first, accept five teams, then add Kanban and validate 11–14-team load.
3. Use fixed sprint boundaries, unchanged carryover, team business-time mechanics, and both
   business/calendar analytics.
4. Use one company-managed project/board per team, virtual identity fields, internal transcripts,
   and no v2 Jira comments.
5. Treat supported manual Jira sprint/card edits as attributed inputs and reconcile Jira before
   advancing after restart; incompatible/protected changes surface a scoped conflict.
6. Keep Codex conversation/control separate from server-key OpenAI content generation and expose
   complete calibration ground truth.
7. Live Jira work requires a designated disposable target and authorization. Code work requires the
   mandatory TDD skill from `AGENTS.md`.

## Critical Gotchas

- Precomputed final issue states are not applied to persistent `Issue` rows.
- A newly generated schedule usually lacks the Jira sprint ID needed for add/start/complete events.
- Event dispatch ignores sprint activation and per-team pause/deactivation.
- Per-team start/resume does not start the global scheduler.
- SimClock speed and tick-interval API changes do not accelerate/reconfigure scheduled dispatch.
- Health recovery can remain stuck in `RECOVERING` because queue recovery is not wired.
- Jira-synchronized sprint edit/delete paths use `app.state.jira_write_queue`, but startup stores
  `app.state.write_queue`.
- Dysfunction and cross-team dependency models do not affect the active simulation.
- Historical documentation claims event-handler modules that no longer exist.
- The API is unauthenticated, and the public deployment has no configured TLS listener.
- V1 has no durable webhook/poll inbox for Jira-side manual sprint/card changes; v2 must not build
  reconciliation on the current one-way dispatcher alone.
- Restart must reconcile supported Jira interventions before boundary handling or new outbound
  delivery, and must not manufacture missed daily work.
- Jira provisioning and sprint creation need explicit idempotency/read-back tests before relying on
  them in autonomous operation.
- Never place simulator/Jira/OpenAI credentials in source, browser bundles, URLs, logs, or evidence.
- V2 projection delivery must consume only committed/read `PENDING` intents after the unit of work;
  never import or invoke an adapter inside `commit_tick_slice`.
- Treat `append_sequence` as the only pagination order. `occurred_at` may be equal or late, and
  semantic replay must not allocate another row when canonical immutable content is identical.
- Existing dirty documentation and untracked assessment/skill files belong to the current owner;
  do not stash, reset, clean, or overwrite them during worktree setup.

## Mandatory Development Flow

For every future change: plan and obtain approval, split and record tasks in `backlog/`, use strict
RED → GREEN → REFACTOR TDD, apply Python clean-code skills, update all mandatory documents, verify
all tests, deploy, and wait for Pavel's UAT/sign-off.
