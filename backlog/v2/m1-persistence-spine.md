# M1 Persistence Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the first durable, isolated v2 persistence spine and prove that one live simulation slice can atomically commit runtime state, evidence, and transport-neutral projection intent.

**Architecture:** V2 is a structurally separate aggregate rooted at `v2_teams` with only `v2_*` persistence tables; it shares SQLAlchemy `Base`, the engine/session factory, and Alembic registration but never joins to legacy `teams`, precomputation, or scheduled events. Task 1 commits a complete canonical Scrum blueprint and initial run/runtime in one transaction; after Task 1 is reviewed and committed at revision 013, Task 2 adds revision 014 and a short optimistic unit of work for live slices. Projection adapters consume committed intents only after the database transaction has ended.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy 2, Alembic, SQLite/WAL, pytest, Ruff.

## Global Constraints

- Follow strict RED -> GREEN -> REFACTOR for every behavior. Run the stated RED command before implementation, retain the failing output, run the identical command after implementation, and retain the passing output under `evidence/v2/`.
- Apply the installed Superpowers TDD skill to all code and the project clean-code skills to all backend Python. Public interfaces have type hints; functions are at most 30 lines and accept at most three arguments; dependencies are injected.
- Finish each task by updating `changelog.md`, `assumptions.md`, `README.md`, `agent_instruction.md`, this file's task marker, and that task's `evidence/v2/` record before committing.
- Encode persisted JSON with one documented `CANONICAL_JSON_V1` rule: UTF-8, sorted object keys, compact separators, no ASCII escaping, preserved array order, and rejection of NaN/infinity. Store the lower-case SHA-256 digest of those exact bytes.
- Derive semantic IDs with UUIDv5 from fixed namespace `0f896a61-4777-57d8-9e81-62c5c4ab2b7f`; never derive replay identity from Python `hash()`, random UUIDs, database row IDs, timestamps, or insertion order.
- Every persisted instant has UTC provenance. Domain inputs and SQLAlchemy bind processing reject naive datetimes; aware inputs are normalized to UTC and reload as `datetime` values with `timezone.utc`.
- All database changes are additive. Do not alter legacy table schemas, legacy model behavior, v1 routes, or v1 engine/integration code; the sole permitted v1-file edit is additive v2 model registration in `backend/app/models/__init__.py`.
- Do not add a runtime discriminator to legacy `teams`. Do not route v2 through `app.engine.precompute`, `scheduled_events`, `PrecomputationRun`, the v1 scheduler, or the v1 Jira write queue.
- Migration 013 must have `down_revision = "012"`, leave one Alembic head, preserve populated revision-012 data byte-for-byte, and completely remove only its own additions on downgrade. Task 2 must use migration 014 because Task 1 owns a reviewed, committed 013.
- Runtime mutation, activity, ground truth, and projection intent commit together. Jira, OpenAI, or any other external adapter is never invoked inside the transaction; this plan adds no Jira/OpenAI transport.
- Work is local only: no live Jira calls, deploy, push, production mutation, UAT claim, or milestone sign-off.

---

Status: COMPLETE

## Task Checklist

- [x] Task 1 — Persist an isolated resolved team blueprint and runtime shell atomically — completed 2026-08-10
- [x] Task 2 — Add the atomic live-slice, evidence, and projection contract — completed 2026-08-10
- [x] Task 2 review fix round 1 — Enforce live-slice invariants — completed 2026-08-10
- [x] Task 2 review fix round 2 — Reject non-string JSON keys — completed 2026-08-10

## Task 1: Persist an isolated resolved team blueprint and runtime shell atomically

**Goal:** Create and reload one complete Scrum team aggregate without writing any legacy team/runtime table and with a reversible 012 -> 013 migration.

**Inputs:** `docs/v2/contracts/team-blueprint.schema.json`, the resolved Scrum example, the approved separate-v2-root decision, an idempotency key, and one aware request timestamp.

**Outputs:** Immutable v2 domain contracts, canonical JSON/hash/UUID helpers, an aware-UTC SQLAlchemy type, four v2 tables, an atomic repository, and a create-team application service.

**Files:**

- Create `backend/app/v2/__init__.py`.
- Create `backend/app/v2/domain/__init__.py`.
- Create `backend/app/v2/domain/canonical_json.py` for `CANONICAL_JSON_V1`, SHA-256, and UUIDv5 helpers.
- Create `backend/app/v2/domain/team_blueprint.py` for the frozen resolved-blueprint models and cross-field validation.
- Create `backend/app/v2/domain/team_runtime.py` for `V2Team`, `V2Run`, `TeamRuntime`, and `PersistedTeamAggregate`.
- Create `backend/app/v2/persistence/__init__.py`.
- Create `backend/app/v2/persistence/utc_datetime.py` for `UTCDateTime`.
- Create `backend/app/v2/persistence/team_models.py` for the four SQLAlchemy mappings only.
- Create `backend/app/v2/persistence/team_repository.py` for the port and SQLAlchemy implementation.
- Create `backend/app/v2/application/__init__.py`.
- Create `backend/app/v2/application/create_team.py` for the use case and typed errors/results.
- Create `backend/alembic/versions/013_add_v2_team_spine.py` with `revision = "013"` and `down_revision = "012"`.
- Modify `backend/app/models/__init__.py` only to import/export the v2 mappings so `Base.metadata` and Alembic see them.
- Create `backend/tests/v2/__init__.py`, `backend/tests/v2/unit/__init__.py`, and `backend/tests/v2/integration/__init__.py`.
- Create `backend/tests/v2/conftest.py` and `backend/tests/v2/fixtures/resolved_scrum_blueprint.json`; the fixture must materialize every value rather than rely on schema/catalog defaults.
- Create `backend/tests/v2/unit/test_team_blueprint.py`, `backend/tests/v2/unit/test_utc_datetime.py`, `backend/tests/v2/unit/test_create_team.py`, and `backend/tests/v2/unit/test_architecture_boundaries.py`.
- Create `backend/tests/v2/integration/test_team_repository.py` and `backend/tests/v2/integration/test_migration_013.py`.

**Interfaces and invariants:**

- `canonical_json(value: JsonValue) -> str`, `canonical_sha256(value: JsonValue) -> str`, and `semantic_uuid(path: str) -> UUID` implement the exact global rules. The team path is `team/<blueprint-sha256>`; the blueprint, initial run, and runtime paths are respectively `blueprint/<team-uuid>/0`, `run/<team-uuid>/0`, and `runtime/<team-uuid>`.
- `ResolvedTeamBlueprint.from_canonical_json(document: str) -> ResolvedTeamBlueprint` rejects a document unless parsing, validation, and re-encoding reproduce the input byte-for-byte. All Pydantic models are frozen, forbid extra keys, and declare fields without defaults.
- The required snapshot sections are `schema_version`, `team`, `jira`, `calendar`, `members`, `workflow`, `timing`, `backlog`, `risks`, `content`, `scrum`, and `seed`; M1 rejects Kanban. `team` includes name, purpose/summary/description, archetype, locale, timezone, and methodology. `jira` includes the resolved project name/key, board name, project type, and topology strategy.
- Calendar requires ordered weekdays, local work interval, holiday profile/version/horizon, and the complete explicit holiday list. Each member requires ordered roles, every responsibility/activity proficiency, daily capacity, WIP limit, and an explicit availability list. Workflow requires all status/Jira mappings and every issue-type route.
- `timing.entries` is a non-empty materialized grid of `(status_key, issue_type, story_points, min, p25, p50, p99, max, touch_min, touch_max)` cells plus its profile/algorithm versions. `risks.rules` materializes each enabled rule's trigger, base probability, coefficients, clamp, and mechanical parameters plus profile/algorithm versions. Catalog references or empty overrides without the resolved cells/rules are incomplete and invalid.
- Backlog stores all target, type/point/priority weights, import choices, and replenishment policy. Scrum stores fixed cadence, first aware boundary, capacity range, planning/ranking/carryover policy versions. Content remains inert configuration and stores its resolved generation/transcript policy; it performs no external call.
- `CreateTeamCommand(idempotency_key: str, blueprint_json: str, requested_at: datetime)` is the only service input. `CreateTeamService.create(command: CreateTeamCommand) -> PersistedTeamAggregate` computes the canonical hash and semantic IDs, creates state `CREATED`, initializes simulation time to `requested_at`, and delegates one atomic write to the repository.
- `V2TeamRepository.create(aggregate: PersistedTeamAggregate) -> PersistedTeamAggregate`, `get_by_id(team_id: UUID) -> PersistedTeamAggregate | None`, and `get_by_idempotency_key(key: str) -> PersistedTeamAggregate | None` are the persistence port. `SqlAlchemyV2TeamRepository` accepts only a session factory and owns commit/rollback; callers never receive ORM objects.
- Same idempotency key plus identical blueprint hash returns the already-persisted aggregate without a write. The same key plus a different hash raises `TeamCreationConflict`. Invalid/noncanonical input raises `InvalidResolvedBlueprint` before a session is opened.
- `v2_teams`: UUID text primary key, unique idempotency key, canonical blueprint hash, name, methodology, and aware `created_at`.
- `v2_team_blueprints`: UUID text primary key, unique `team_id` FK with cascade, schema version, canonical JSON text, SHA-256, and aware `recorded_at`.
- `v2_runs`: UUID text primary key, `team_id` FK with cascade, zero-based run ordinal, explicit `CREATED` state, and aware `created_at`; `(team_id, ordinal)` is unique.
- `v2_team_runtimes`: semantic UUID primary key, unique `team_id` and `run_id` FKs with cascade, explicit `CREATED` state, simulation time, nullable next wake, and aware created/updated instants. Runtime versioning intentionally belongs to Task 2/migration 014.

**RED command and required failures:**

- [ ] Create the fixture and tests first, then from `backend/` run this exact command with `set -o pipefail`; retain its non-zero output in `evidence/v2/M1-T01/red.txt`:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_team_blueprint.py tests/v2/unit/test_utc_datetime.py tests/v2/unit/test_create_team.py tests/v2/unit/test_architecture_boundaries.py tests/v2/integration/test_team_repository.py tests/v2/integration/test_migration_013.py -q 2>&1 | tee ../evidence/v2/M1-T01/red.txt
  ```

- [ ] Confirm RED is caused by missing v2 modules/revision 013, not a malformed fixture or test setup.
- [ ] Cover canonical round-trip and stable golden JSON/hash/UUID vectors; reject reordered/whitespace-altered JSON, missing sections/materialized cells/rules, extra keys, Kanban, and non-finite numbers.
- [ ] Cover `UTCDateTime` normalization/reload and rejection of naive command, blueprint-boundary, ORM, and repository datetimes.
- [ ] Cover atomic creation of exactly one row in each core table, restart through a disposed/new engine and session factory, same-key/same-hash idempotency, same-key/different-hash conflict, and constraint/injected-final-INSERT failure rolling back all four tables.
- [ ] Cover v1 invisibility: seed one legacy `Team`, create one v2 team, and prove `select(Team)` plus `GET /teams` return only the legacy row while all v2 rows remain reloadable through the v2 repository.
- [ ] Cover the dependency boundary with an AST/import test: `app.v2` may import `app.models.base` and `app.database`, but no legacy model other than `Base`, no `app.engine`, no `app.integrations`, and specifically no precompute/scheduled-event/Jira queue symbol.
- [ ] In a populated revision-012 database, seed representative rows in every legacy table, snapshot ordered row content and legacy table/column/index/FK metadata, upgrade to 013, and prove the snapshot is unchanged. Downgrade 013 -> 012, prove all four v2 tables are gone and the legacy snapshot is still unchanged, then re-upgrade to 013 and prove one head and all four empty v2 tables return.

**Implementation steps:**

- [ ] Implement the frozen blueprint hierarchy and cross-field validation just deeply enough to accept the resolved fixture and reject every RED case; do not resolve defaults or catalogs in persistence.
- [ ] Implement canonical serialization, digest, and semantic IDs with fixed golden vectors.
- [ ] Implement `UTCDateTime` and use it for every v2 instant in both ORM mappings and migrations.
- [ ] Add the four isolated mappings, explicit uniqueness/FKs/indexes, and additive registration.
- [ ] Implement repository mapping and one `sessionmaker.begin()` transaction; translate only recognized uniqueness conflicts into the typed idempotency result/conflict and re-raise unexpected database failures after rollback.
- [ ] Implement `CreateTeamService` as validation/hash/ID orchestration with no SQLAlchemy, legacy engine, Jira, or OpenAI dependency.
- [ ] Implement migration 013 in FK-safe upgrade order and exact reverse downgrade order; do not copy revision 012's partial/idempotent downgrade pattern.
- [ ] Run the identical RED command and retain passing output as `evidence/v2/M1-T01/green.txt`; refactor only while it stays green.

**Verification, documentation, and evidence:**

- [ ] From `backend/`, append outputs to `evidence/v2/M1-T01/verification.txt` for the targeted command, full safe backend suite, `../.venv/bin/python -B -m ruff check --no-cache .`, and Alembic `heads --verbose`, `branches --verbose`, and `history` with a disposable SQLite `DATABASE_URL`.
- [ ] Record the RED reason, GREEN result, migration round-trip, legacy snapshot proof, restart proof, exact commands, and environment in `evidence/v2/M1-T01/README.md`; do not include secrets or live-provider evidence.
- [ ] Append the task result to `changelog.md` and assumptions to `assumptions.md`; update `README.md` to describe only the now-implemented v2 persistence shell and local commands; update `agent_instruction.md` with revision 013, key files, constraints, and Task 2 as next.
- [ ] Mark Task 1 complete above with date 2026-08-10 while leaving M1 in progress, inspect the staged diff, and commit exactly this task as `feat(v2): persist isolated team runtime shell` before Task 2 begins.

**Done condition:** Revision 013 is the sole head; a fully resolved canonical Scrum blueprint creates and restart-reloads one isolated team/blueprint/run/runtime aggregate atomically; invalid, naive, conflicting, and injected-failure cases leave no partial rows; populated v1 data/schema remains unchanged and invisible in the opposite direction; targeted/full tests and Ruff pass with captured evidence.

## Task 2: Add the atomic live-slice, evidence, and projection contract

**Goal:** Commit one boundary-bounded runtime advance, ordered activity, immutable ground truth, and generic pending projection intents atomically under optimistic concurrency, without invoking an external adapter.

**Dependency:** Begin only from Task 1's reviewed commit with Alembic head 013. This task owns a separate migration 014 so the persistence shell and live-slice transaction remain independently reviewable.

**Inputs:** `PersistedTeamAggregate`/`TeamRuntime` from Task 1, an expected runtime version, caller-ordered activity/evidence/intent drafts, and one aware commit timestamp.

**Outputs:** Immutable live-slice domain contracts, three append-oriented v2 tables, runtime version 0 -> N, cursor pagination, and `V2UnitOfWork`.

**Files:**

- Create `backend/app/v2/domain/live_slice.py` for draft/stored records, page queries/results, `RuntimeAdvance`, `TickSliceCommit`, and `CommittedTickSlice`.
- Modify `backend/app/v2/domain/team_runtime.py` to expose the persisted optimistic `version` after migration 014.
- Create `backend/app/v2/persistence/live_models.py` for activity, ground-truth, and projection-intent mappings only.
- Create `backend/app/v2/persistence/unit_of_work.py` for the `V2UnitOfWork` port and `SqlAlchemyV2UnitOfWork`.
- Modify `backend/app/v2/persistence/team_models.py` and `backend/app/v2/persistence/team_repository.py` to write/read runtime version explicitly for newly created and existing aggregates.
- Modify `backend/app/v2/domain/__init__.py`, `backend/app/v2/persistence/__init__.py`, and `backend/app/models/__init__.py` only for additive exports/model registration.
- Create `backend/alembic/versions/014_add_v2_live_slice_ledgers.py` with `revision = "014"` and `down_revision = "013"`.
- Create `backend/tests/v2/unit/test_live_slice.py`, `backend/tests/v2/integration/test_unit_of_work.py`, `backend/tests/v2/integration/test_projection_boundary.py`, and `backend/tests/v2/integration/test_migration_014.py`.

**Interfaces and invariants:**

- `RuntimeAdvance(state: str, simulation_time: datetime, next_wake_at: datetime | None)` carries only the proposed mutable runtime values. `TickSliceCommit` contains `commit_id`, `team_id`, `run_id`, `expected_runtime_version`, `runtime_after`, ordered tuples `activity`, `ground_truth`, and `projection_intents`, plus aware `recorded_at`.
- `ActivityEventDraft`, `GroundTruthRecordDraft`, and `ProjectionIntentDraft` each require a non-empty semantic deduplication key, schema/type identifiers, aware `occurred_at`, and a JSON payload. Activity also requires aggregate type/id/version; evidence requires record/provenance type; projection requires target kind, operation type, aggregate id/version, and explicit `PENDING` state.
- Draft factories derive record UUIDv5 paths `activity/<semantic-key>`, `ground-truth/<semantic-key>`, and `projection/<semantic-key>` and precompute canonical payload/hash. A supplied ID/hash mismatch, naive timestamp, invalid JSON, or duplicate semantic key with different canonical content rejects the entire commit.
- `V2UnitOfWork.commit_tick_slice(commit: TickSliceCommit) -> CommittedTickSlice`, `get_runtime(team_id: UUID) -> TeamRuntime`, `page_activity(query: LedgerPageQuery) -> ActivityPage`, `page_ground_truth(query: LedgerPageQuery) -> GroundTruthPage`, and `page_projection(query: ProjectionPageQuery) -> ProjectionPage` are the only public persistence operations. Query objects carry `team_id`, optional `run_id`, `after_sequence`, and bounded `limit`, keeping method argument counts within the global limit.
- The commit performs a single compare-and-swap update: `WHERE team_id = :team_id AND run_id = :run_id AND version = :expected`; it writes the proposed runtime and increments version by one. Zero updated rows raises `StaleRuntimeVersion` and inserts nothing.
- Within one successful transaction, tuple position becomes `transaction_sequence`; each table assigns its own monotonically increasing integer `append_sequence`. Pagination orders only by `append_sequence`, uses an exclusive `after_sequence` cursor, and is stable for equal or late `occurred_at` values.
- Same semantic key plus identical canonical type/payload is a stable no-op that returns the existing record; the same key plus different content raises `SemanticDeduplicationConflict` and rolls back the runtime update and every new record.
- `v2_activity_events`: integer append-sequence primary key, semantic UUID, team/run/commit IDs, transaction sequence, unique semantic key, schema/event/aggregate identity and version, UTC occurred/recorded times, canonical payload text, and payload hash.
- `v2_ground_truth_records`: the same envelope with record/provenance type in place of event/aggregate fields; rows are append-only and corrections are new records.
- `v2_projection_intents`: the same envelope with target/operation/aggregate fields and explicit status; it stores generic local intent only, with no Jira/OpenAI payload class or client reference.
- Migration 014 temporarily backfills existing `v2_team_runtimes.version` to 0, then leaves it non-null with no hidden database default; new runtime creation writes 0 explicitly. Downgrade removes the three tables and version column while preserving all revision-013 rows.
- Define a test-only `ProjectionAdapter` fake protocol with `deliver(intent)`. It is deliberately absent from `V2UnitOfWork` construction/imports; callers may invoke it only with a record returned from a completed commit/read.

**RED command and required failures:**

- [ ] Write tests first, then from `backend/` run this exact command with `set -o pipefail`; retain non-zero output in `evidence/v2/M1-T02/red.txt`:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 INTEGRATION_TESTS=false ../.venv/bin/python -B -m pytest -p no:cacheprovider tests/v2/unit/test_live_slice.py tests/v2/integration/test_unit_of_work.py tests/v2/integration/test_projection_boundary.py tests/v2/integration/test_migration_014.py -q 2>&1 | tee ../evidence/v2/M1-T02/red.txt
  ```

- [ ] Confirm RED is caused by missing live-slice modules/revision 014, not Task 1 regression or fixture setup.
- [ ] Prove one commit advances version 0 -> 1 and atomically persists runtime, two same-type/same-version activity events in caller order, two evidence records, and two pending intents.
- [ ] Inject a database failure successively on runtime, activity, ground-truth, and projection writes; after each failure, assert the original runtime/version and all three ledgers are unchanged.
- [ ] Load the same version through two unit-of-work instances, commit the first, and prove the second raises `StaleRuntimeVersion` with zero partial writes.
- [ ] Prove identical semantic replay is a no-op, conflicting replay rolls back, same timestamps preserve tuple/insertion order, late `occurred_at` values remain after an issued cursor, limits/cursors have no gaps or duplicates, and cross-team/run references fail.
- [ ] Dispose the engine, construct a fresh engine/session factory/unit of work, and prove runtime version, append order, canonical payload/hash, pending intents, and next cursors reload unchanged.
- [ ] After a successful commit returns, call an exploding fake projection adapter; prove the adapter failure cannot undo or mutate the committed runtime, activity, evidence, or pending intent. Add an import/spy assertion that the adapter was never called during `commit_tick_slice`.
- [ ] Upgrade a populated 013 database to 014, verify version backfill and legacy/v2 Task-1 row preservation, downgrade 014 -> 013, verify only Task-2 additions are gone, then re-upgrade to sole head 014.

**Implementation steps:**

- [ ] Implement frozen live-slice/draft/query/result contracts, aware-time and canonical-payload validation, semantic UUID derivation, and contiguous transaction ordering.
- [ ] Add the three mappings, FK/unique/check/index constraints for team/run, semantic key, append pagination, and pending projection lookup.
- [ ] Implement migration 014 in FK-safe order; use an explicit temporary backfill/rebuild path so the final `version` column has no server default and downgrade restores the exact 013 runtime table.
- [ ] Implement `SqlAlchemyV2UnitOfWork` with one short transaction, compare-and-swap runtime update, deterministic dedup resolution, ordered inserts, explicit rollback, and domain-only return objects.
- [ ] Keep projection delivery outside the unit of work and add no transport/worker. Refactor shared mapping/canonical helpers only while Task 1 and Task 2 targeted suites remain green.
- [ ] Run the identical RED command and retain passing output as `evidence/v2/M1-T02/green.txt`; refactor only while it stays green.

**Verification, documentation, and evidence:**

- [ ] From `backend/`, append outputs to `evidence/v2/M1-T02/verification.txt` for both Task 1 and Task 2 targeted commands, the full safe backend suite, Ruff, and Alembic graph plus disposable 013 -> 014 -> 013 -> 014 checks.
- [ ] Record RED/GREEN, rollback injection points, stale-writer result, dedup/order/pagination/restart proof, fake-adapter failure, migration round-trip, exact commands, and environment in `evidence/v2/M1-T02/README.md`.
- [ ] Append the task result to `changelog.md` and assumptions to `assumptions.md`; update `README.md` to describe only the committed live-slice contract; update `agent_instruction.md` with revision 014, interfaces, constraints, and the next approved M1 slice (not a speculative roadmap).
- [ ] Mark Task 2 complete above with date 2026-08-10 while leaving M1 unchecked until all M1 acceptance work is complete, inspect the staged diff, and commit exactly this task as `feat(v2): commit live slices atomically`.

**Done condition:** Revision 014 is the sole head; concurrent stale writers cannot overwrite runtime; one successful live slice atomically and restart-safely advances runtime and appends deterministic ordered activity, evidence, and pending generic projection intent; rollback/dedup/pagination cases are proven; an external fake failure occurs only after commit and cannot corrupt authoritative state; all targeted/full tests and Ruff pass with captured evidence.

### Task 2 review fix round 1

The completed review fix makes direct/replaced drafts and the UOW boundary enforce canonical
identity/content before session creation; makes payload aliases deeply immutable; registers all
seven v2 tables from every fresh public import order; translates identical/differing semantic-key
insert races to no-op/typed outcomes with whole-slice rollback; and explicitly reloads ground truth
after the test-only post-commit adapter failure. Supplemental evidence runs the committed migration
014 test against Task-1 base `ee48c5d` and retains the expected missing-014 failure. M1 remains
`IN PROGRESS`; no later engine slice, UAT, deployment, or milestone completion was claimed.

### Task 2 review fix round 2

The completed narrow fix rejects integer, boolean, `None`, mixed, and recursively nested non-string
mapping keys at the live-slice envelope/factory boundary before canonical encoding or session
creation. Valid canonical bytes, hashes, payload immutability, transaction behavior, revision 014,
and every earlier fix remain unchanged. M1 remains `IN PROGRESS`.
