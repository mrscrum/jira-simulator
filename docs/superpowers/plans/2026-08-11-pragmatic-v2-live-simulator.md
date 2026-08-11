# Pragmatic v2 Live Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first persisted v2 Scrum loop: coherent bootstrap/reload, plausible incremental work, fixed sprint boundaries, autonomous restart-safe scheduling, and retryable fake-Jira projection.

**Architecture:** One sequential scheduler discovers configured active teams and invokes the same independent team operation for each. A pure Scrum kernel produces after-images plus activity, ground truth, and Jira intents; the accepted Task 6 unit of work commits them atomically, and a separate worker delivers committed intents through the existing `JiraClient`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2/Alembic, SQLite, APScheduler, Pydantic v2, pytest, Ruff, and the existing async `JiraClient`/httpx transport.

## Global Constraints

- The authority is the [approved pragmatic design](../specs/2026-08-11-pragmatic-v2-live-simulator-design.md); accepted v2 Tasks 1–6 are frozen. Call their public interfaces and make only a narrowly tested integration correction if live-loop behavior exposes a real defect.
- V2 blueprint, runtime, Scrum state, activity, ground truth, and projection intents remain authoritative. Do not read from or write to v1 team/sprint/issue/scheduled-event state in this path.
- Follow RED -> GREEN -> REFACTOR for every production behavior. Before each task, mark its exact backlog entry in progress; after each task update `changelog.md`, `assumptions.md`, `README.md`, `agent_instruction.md`, and the relevant `backlog/v2/*.md` status before committing.
- `ResolvedTeamBlueprint` is configuration authority. Team count is configuration: one team covers functional behavior, two differently configured teams cover isolation, and five teams are optional later UAT/load only.
- Use ordinary aware UTC `datetime`/`timedelta` arithmetic in new mechanics and convert at existing persisted microsecond fields. Do not expand exact-arithmetic, HMAC/canonical-proof, hostile-subclass, pickle, reconstruction, or replay machinery.
- One committed tick is atomic and contains runtime CAS, Scrum after-images, activity, ground truth, and pending Jira intents. No Jira call occurs in that transaction; a stale runtime version gets one reload/retry only.
- Scheduler work is sequential until measurement justifies bounded parallelism. Downtime records a gap and credits no missed work; no multi-writer, HA, partition-invariance, or catch-up-work design is in scope.
- Tasks 1–3 create no migration and leave revision 015 unchanged. Task 4 creates revision 016 containing only v2 Jira delivery receipts and resource mappings. Task 5 adds no schema.
- Work is local and fake-provider only. Do not deploy, mutate production Jira, access credentials, run UAT, or push without separate authorization.

## Execution Preflight

The worktree currently contains preserved, superseded Task 7 artifacts. Before executing this plan, hide only those paths in a named stash; do not use a whole-worktree stash:

```bash
git stash push -u -m "superseded-v2-task7-before-pragmatic-live-loop" -- \
  backend/tests/v2/unit/test_scrum_state.py \
  backend/tests/v2/capacity_allocator_support.py \
  backend/tests/v2/unit/test_capacity_allocator.py \
  backend/tests/v2/unit/test_duration_math.py \
  evidence/v2/M1-T07
git stash list --format='%gd %s' | head
```

Then add these five outcomes to the relevant v2 backlog files before production work. Stage only named task files and required documentation at every commit; never stage the preserved stash or unrelated work.

---

### Task 1: Coherent Read and Idempotent Scrum Bootstrap

**Files:**
- Create: `backend/app/v2/domain/draw_source.py`
- Create: `backend/app/v2/domain/scrum_bootstrap.py`
- Create: `backend/app/v2/application/live_team.py`
- Create: `backend/app/v2/persistence/live_team_store.py`
- Create: `backend/tests/v2/unit/test_scrum_bootstrap.py`
- Create: `backend/tests/v2/integration/test_live_team_store.py`
- Update after GREEN: required root docs plus `backlog/v2/README.md` and `backlog/v2/stage-1-live-runtime-and-scrum.md`

**Interfaces:**

```python
class DrawSource(Protocol):
    def unit(self, decision: DecisionOccurrence, draw_index: int = 0) -> float: ...

@dataclass(frozen=True)
class LiveTeamState:
    aggregate: PersistedTeamAggregate
    scrum: ScrumStateSnapshot

def build_initial_scrum_state(
    aggregate: PersistedTeamAggregate, started_at: datetime, draws: DrawSource
) -> ScrumStateWriteSet: ...

class LiveTeamStore(Protocol):
    def load(self, team_id: UUID) -> LiveTeamState: ...
    def ensure_bootstrapped(self, team_id: UUID, started_at: datetime) -> LiveTeamState: ...
```

`SeededDrawSource` is the small adapter over the accepted Task 3 stream. `SqlAlchemyLiveTeamStore` performs each load in one transaction and calls the accepted `SqlAlchemyScrumStateMapper` with its caller-owned session. Bootstrap creates member identities, ranked target-depth backlog, one fixed-boundary active sprint, selected scope, initial route visits and samples, and a `RUNNING` runtime with its first wake. A repeated call returns the same rows; an injected failure rolls back runtime and all Scrum rows. No migration.

- [ ] **RED:** Add one-team tests for deterministic complete bootstrap, idempotency, rollback, and a detached complete reload after a new session/process boundary.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_scrum_bootstrap.py tests/v2/integration/test_live_team_store.py -q`

  Expected: non-zero because the live-team interfaces do not exist.

- [ ] **GREEN/REFACTOR:** Implement only the interfaces above using blueprint weights/routes/timing and the Task 5 mapper; keep the coherent read transaction short.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_scrum_bootstrap.py tests/v2/integration/test_live_team_store.py tests/v2/integration/test_scrum_state_mapper.py -q`

- [ ] **Verify/docs/commit:** Run `cd backend && ../.venv/bin/python -m ruff check app/v2 tests/v2`, update required docs, stage named paths only, and commit `feat: bootstrap coherent v2 team state`.

### Task 2: Pragmatic Incremental Scrum Tick and Atomic Commit

**Files:**
- Create: `backend/app/v2/domain/scrum_tick.py`
- Create: `backend/app/v2/application/team_tick.py`
- Create: `backend/tests/v2/unit/test_scrum_tick.py`
- Create: `backend/tests/v2/integration/test_team_tick.py`
- Update after GREEN: required root docs plus `backlog/v2/README.md` and `backlog/v2/stage-1-live-runtime-and-scrum.md`

**Interfaces:**

```python
@dataclass(frozen=True)
class TickRequest:
    team_id: UUID
    ends_at: datetime
    recorded_at: datetime

def calculate_scrum_tick(
    state: LiveTeamState, request: TickRequest, draws: DrawSource
) -> AuthoritativeTickSliceCommit: ...

class TeamTickService:
    def advance(self, request: TickRequest) -> CommittedAuthoritativeTickSlice: ...
```

The pure calculation uses `BusinessCalendar` and existing status samples. It retains eligible owners; assigns by configured responsibility/proficiency and rank; enforces availability, daily capacity, and `max_concurrent_wip`; records queue separately from pause and credited touch; and completes a visit only after sampled dwell and touch are satisfied. It opens the next type-specific route step, including zero-touch terminal steps, and emits readable activity, causal ground truth, and Jira intents. New arithmetic is proportional duration arithmetic, not the abandoned exact-credit protocol. `TeamTickService` loads coherently, calls `V2UnitOfWork.commit_authoritative_slice`, and reloads/retries exactly once on `StaleRuntimeVersion`. No migration or network call.

- [ ] **RED:** Add focused examples for responsibility, unavailable members, daily capacity, WIP, sticky ownership, queue/dwell versus touch, deterministic same-state choices, forward route completion, and rejection-free ordinary progress; add atomic success and whole-transaction rollback tests.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_scrum_tick.py tests/v2/integration/test_team_tick.py -q`

  Expected: non-zero because the tick calculation/service do not exist.

- [ ] **GREEN/REFACTOR:** Implement the smallest kernel and service that satisfy those observable examples and construct the accepted Task 6 command without modifying its contract.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_scrum_tick.py tests/v2/integration/test_team_tick.py tests/v2/integration/test_authoritative_unit_of_work.py -q`

- [ ] **Verify/docs/commit:** Run Ruff plus `cd backend && ../.venv/bin/python -m pytest tests/v2 -q`, update required docs, stage named paths only, and commit `feat: advance v2 scrum ticks`.

### Task 3: Fixed Sprint Lifecycle, Due-Team Scheduler, and Restart

**Files:**
- Create: `backend/app/v2/domain/sprint_lifecycle.py`
- Create: `backend/app/v2/application/live_scheduler.py`
- Create: `backend/app/v2/persistence/due_team_store.py`
- Create: `backend/app/v2/runtime.py`
- Modify: `backend/app/v2/domain/scrum_tick.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/v2/unit/test_v2_sprint_lifecycle.py`
- Create: `backend/tests/v2/integration/test_live_scheduler.py`
- Update after GREEN: required root docs plus `backlog/v2/README.md` and `backlog/v2/stage-1-live-runtime-and-scrum.md`

**Interfaces:**

```python
@dataclass(frozen=True)
class SprintTransition:
    state: ScrumStateWriteSet
    activity: tuple[ActivityEventDraft, ...]
    ground_truth: tuple[GroundTruthRecordDraft, ...]
    projection_intents: tuple[ProjectionIntentDraft, ...]

def cross_sprint_boundary(state: LiveTeamState, boundary: datetime) -> SprintTransition: ...

class DueTeamStore(Protocol):
    def due_team_ids(self, as_of: datetime, limit: int = 100) -> tuple[UUID, ...]: ...
    def running_team_ids(self) -> tuple[UUID, ...]: ...

@dataclass(frozen=True)
class SchedulerRunResult:
    attempted: tuple[UUID, ...]
    succeeded: tuple[UUID, ...]
    failed: tuple[UUID, ...]

class ReconcileBeforeResume(Protocol):
    def reconcile(self, team_id: UUID, as_of: datetime) -> None: ...

class LiveScheduler:
    def run_due(self, as_of: datetime) -> SchedulerRunResult: ...
    def resume_after_restart(self, as_of: datetime) -> SchedulerRunResult: ...
```

At a fixed boundary, close once; preserve every unfinished item's status, owner, visit/sample, and progress; put carryover ahead of newly selected ranked backlog; then emit dependency-ordered sprint complete/create/scope/start intents. `run_due` processes sorted configured teams sequentially and isolates errors. `resume_after_restart` invokes the injected supported-observation reconciler first, records `[runtime.simulation_time, as_of)` as downtime, advances overdue lifecycle boundaries with zero work credit, and schedules from `as_of`; pending intents remain untouched. `runtime.py` registers the APScheduler job without creating a second team-count path. No migration.

- [ ] **RED:** Test unchanged carryover, exactly-once boundary handling, intent dependency order, one-team due execution, two-team configuration/isolation when one fails, and restart with no downtime capacity/touch credit and reconciliation-before-progress.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_v2_sprint_lifecycle.py tests/v2/integration/test_live_scheduler.py -q`

  Expected: non-zero because lifecycle and scheduler interfaces do not exist.

- [ ] **GREEN/REFACTOR:** Implement fixed lifecycle and the sequential persisted scheduler; use the same `TeamTickService` for every team and keep failure recording team-scoped.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_v2_sprint_lifecycle.py tests/v2/integration/test_live_scheduler.py tests/v2/integration/test_team_tick.py -q`

- [ ] **Verify/docs/commit:** Run Ruff plus all v2 tests, update required docs, stage named paths only, and commit `feat: schedule fixed v2 sprints`.

### Task 4: Revision 016 and Retryable v2 Jira Delivery

**Files:**
- Create: `backend/alembic/versions/016_add_v2_jira_delivery_state.py`
- Create: `backend/app/v2/domain/jira_delivery.py`
- Create: `backend/app/v2/persistence/jira_delivery_models.py`
- Create: `backend/app/v2/persistence/jira_delivery_store.py`
- Create: `backend/app/v2/integrations/jira_intent_adapter.py`
- Create: `backend/app/v2/integrations/jira_delivery_worker.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/v2/runtime.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/v2/integration/test_migration_016.py`
- Create: `backend/tests/v2/unit/test_jira_delivery_worker.py`
- Create: `backend/tests/v2/integration/test_jira_delivery_store.py`
- Update after GREEN: required root docs plus `backlog/v2/README.md` and `backlog/v2/stage-2-jira-convergence.md`

**Interfaces:**

```python
@dataclass(frozen=True)
class JiraResourceMapping:
    team_id: UUID
    internal_kind: str
    internal_id: UUID
    jira_id: str
    jira_key: str | None

@dataclass(frozen=True)
class PendingJiraIntent:
    intent: ProjectionIntent
    dependency_keys: tuple[str, ...]
    attempts: int

@dataclass(frozen=True)
class JiraDeliverySuccess:
    intent_id: UUID
    mappings: tuple[JiraResourceMapping, ...]
    canonical_response: str
    delivered_at: datetime

@dataclass(frozen=True)
class JiraDeliveryFailure:
    intent_id: UUID
    retry_at: datetime
    error: str
    failed_at: datetime

@dataclass(frozen=True)
class DeliveryBatchResult:
    attempted: int
    delivered: int
    deferred: int
    failed: int

class JiraDeliveryStore(Protocol):
    def pending(self, as_of: datetime, limit: int = 50) -> tuple[PendingJiraIntent, ...]: ...
    def record_success(self, result: JiraDeliverySuccess) -> None: ...
    def record_failure(self, result: JiraDeliveryFailure) -> None: ...

class JiraIntentAdapter(Protocol):
    async def deliver(self, intent: PendingJiraIntent) -> JiraDeliverySuccess: ...

class JiraDeliveryWorker:
    async def drain_once(self, as_of: datetime, limit: int = 50) -> DeliveryBatchResult: ...
```

Revision 016 adds exactly `v2_jira_delivery_receipts` (intent ID/state, attempts, retry time, delivered time, last error, canonical response) and `v2_jira_resource_mappings` (team, internal kind/ID, Jira ID/key), with ownership/uniqueness/indexes and a populated-015 round trip. It does not alter authoritative state or projection-intent rows. The store selects undelivered due intents in append order and releases an intent only after all `depends_on` semantic keys have delivered receipts. The adapter reuses existing `JiraClient` methods; create operations first resolve a stable v2 marker/mapping so retry after a crash cannot duplicate resources. The worker is sequential, paced, maps 429 to `retry_after`, records other failures as retryable, and never changes committed simulation state.

- [ ] **RED:** Add migration parity/round-trip tests and fake-client tests for dependency order, stable resource reuse, successful receipt, provider error, 429 pacing, restart retry, and exactly-once convergence.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/integration/test_migration_016.py tests/v2/unit/test_jira_delivery_worker.py tests/v2/integration/test_jira_delivery_store.py -q`

  Expected: non-zero because revision 016 and delivery interfaces do not exist.

- [ ] **GREEN/REFACTOR:** Implement only the two-table migration, store, adapter, and worker; register the worker job after startup reconciliation and outside tick transactions.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/integration/test_migration_016.py tests/v2/unit/test_jira_delivery_worker.py tests/v2/integration/test_jira_delivery_store.py tests/unit/test_jira_client.py -q && ../.venv/bin/python -m alembic heads`

  Expected: tests pass and the sole head is `016`.

- [ ] **Verify/docs/commit:** Run Ruff plus all v2 tests, update required docs, stage named paths only, and commit `feat: deliver v2 jira intents`.

### Task 5: First Realism Behaviors and Fake-Jira Vertical Acceptance

**Files:**
- Create: `backend/app/v2/domain/risks.py`
- Modify: `backend/app/v2/domain/scrum_tick.py`
- Create: `backend/tests/v2/unit/test_risks.py`
- Create: `backend/tests/v2/acceptance/test_live_scrum_fake_jira.py`
- Create: `backend/tests/v2/fakes/fake_jira_client.py`
- Update after GREEN: required root docs plus `backlog/v2/README.md`, `backlog/v2/stage-1-live-runtime-and-scrum.md`, and `backlog/v2/stage-4-risks-content-transcripts.md`

**Interfaces:**

```python
@dataclass(frozen=True)
class RiskEvaluation:
    state: ScrumStateWriteSet
    activity: tuple[ActivityEventDraft, ...]
    ground_truth: tuple[GroundTruthRecordDraft, ...]
    projection_intents: tuple[ProjectionIntentDraft, ...]

def evaluate_due_risks(
    state: LiveTeamState, as_of: datetime, draws: DrawSource
) -> RiskEvaluation: ...
```

Evaluate versioned blueprint rules only at their due trigger. Persist mechanical outcomes through existing state: sampled long-stay evidence, review/QA/PO rejection to a configured earlier route step with retained prior history, cancellation, deterministic external-dependency pause, and member-unavailability overlays. Probability inputs include relevant size/quality/complexity/dependency/rework/availability factors; ground truth records configuration, draw, eligible people, wait/progress delta, cause, and Jira intent. Language-model output is not called and never decides mechanics; deterministic fallback text is used. No new migration or modification of accepted Tasks 1–6 contracts.

- [ ] **RED:** Add one focused test per behavior and a vertical fake-Jira scenario that bootstraps one team, advances multiple ticks across two sprint boundaries, restarts without catch-up work, survives a provider outage, drains retained intents, and finishes with no duplicate Jira resources. Re-run the Task 3 two-team isolation test; do not add a five-team correctness matrix.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py tests/v2/integration/test_live_scheduler.py -q`

  Expected: non-zero because risk evaluation and the vertical fake are absent.

- [ ] **GREEN/REFACTOR:** Implement causal outcomes as a focused policy called by the existing tick kernel, then make the fake-Jira vertical pass without provider-specific shortcuts in production code.

  Run: `cd backend && ../.venv/bin/python -m pytest tests/v2/unit/test_risks.py tests/v2/acceptance/test_live_scrum_fake_jira.py tests/v2/integration/test_live_scheduler.py -q`

- [ ] **Final verification/docs/commit:** Run `cd backend && ../.venv/bin/python -m pytest tests/v2 -q && ../.venv/bin/python -m ruff check app/v2 tests/v2 && ../.venv/bin/python -m alembic heads`, update required docs, stage named paths only, and commit `feat: prove v2 live scrum loop`.

## Plan Self-Review Gate

Before execution handoff, confirm: all approved first-loop requirements map to one of the five tasks; there are no placeholders or undefined cross-task types; every later interface matches its first definition; all links resolve; `rg '^### Task '` returns five lines; `wc -l` is at most 350; and `git diff --check` is clean. Async generated content/transcripts, inbound intervention breadth, Kanban, dashboard work, live Jira, deployment, and five-team UAT remain later roadmap slices rather than hidden acceptance for this loop.
