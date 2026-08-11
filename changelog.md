## [2026-03-16] Stage 4 — Simulation Engine

### Added
- Created `engine/calendar.py` — pure functions for timezone-aware business day/working hours calculations (ZoneInfo, holidays, cross-timezone handoff lag)
- Created `engine/capacity.py` — DailyCapacityState frozen dataclass, WIP tracking, touch-time advancement, available worker selection
- Created `engine/issue_state_machine.py` — IssueState StrEnum (9 states), JiraWriteAction dataclass, transition_issue() with valid transition map
- Created `engine/sprint_lifecycle.py` — SprintPhase StrEnum, phase advancement logic, capacity-fitted/priority-ordered issue selection, carry-over detection, velocity calculation
- Created `engine/events/base.py` — TickContext, EventOutcome dataclasses, BaseEvent ABC
- Created `engine/events/registry.py` — event handler registry with 16 events registered
- Created 16 event handlers: carry_over, velocity_drift, sprint_goal_risk, stale_issue, move_left, descope, unplanned_absence, priority_change, split_story, external_block, uneven_load, review_bottleneck, onboarding_tax, late_planning, skipped_retro, scope_commitment_miss
- Created `engine/backlog.py` — depth check, story point distribution, TemplateContentGenerator, OpenAIContentGenerator (fallback to templates), async batch generation
- Created `engine/simulation.py` — SimulationEngine tick orchestrator with state machine (STOPPED/RUNNING/PAUSED), per-team pause, write queue integration, tick counting
- Added 4 new DB models: SimulationEventConfig, SimulationEventLog, MoveLeftConfig (with MoveLeftTarget + MoveLeftSameStepStatus), DailyCapacityLog
- Added 8 columns to Team model (sprint_length_days, sprint_planning_strategy, backlog_depth_target, etc.)
- Added timezone column to Member model
- Added 7 columns to Sprint model (phase, sprint_number, committed_points, completed_points, etc.)
- Added 4 columns to Issue model (backlog_priority, carried_over, descoped, split_from_id)
- Created Alembic migration 008_stage4_schema
- Updated Pydantic schemas for Team, Member, Sprint, Issue with all new fields
- Rewired simulation API router: 20+ endpoints for engine control, per-team control, sprint management, event config, event log, backlog, capacity, engine health
- Created SimulationEngine in FastAPI lifespan and stored on app.state
- Updated health endpoint stage to "4"
- 518 tests passing (229 new), ruff clean

## [2026-03-15] Stage 3 — Jira Integration Layer
### Changed
- Created JiraClient async httpx wrapper (all Jira REST API v3 methods)
- Created JiraHealthMonitor with ONLINE/OFFLINE/RECOVERING state machine
- Created JiraWriteQueue persistent queue with pacing, recovery, and priority ordering
- Created JiraBootstrapper idempotent project/board/field/status provisioner
- Created AlertingService with AWS SES email alerts and daily digest
- Created APScheduler integration (health check every 60s, daily digest at 08:00 UTC)
- Added 4 new DB models: JiraConfig, JiraWriteQueueEntry, JiraIssueMap, JiraIssueLink
- Added 3 bootstrap columns to Team model (jira_bootstrapped, jira_bootstrap_warnings, jira_bootstrapped_at)
- Created 5 Alembic migrations (003-007)
- Added 6 new API endpoints: bootstrap, bootstrap status, health, queue status, retry-failed, project statuses
- Replaced hardcoded jira_proxy.py with real Jira status proxy (with fallback)
- Added Pydantic schemas for all Jira API responses
- Added boto3 dependency for AWS SES
- Added alert_email_from, alert_email_to, aws_ses_region to Settings
- Wired all integration services into FastAPI lifespan
- Updated health endpoint to stage "3"
- 289 tests passing, ruff clean

## [2026-03-15] Stage 1 — Data Model & Database Layer
### Changed
- Implemented Pydantic Settings config module (config.py) loading all env vars
- Implemented database module (database.py) with SQLAlchemy engine, session factory, get_db dependency
- SQLite WAL mode and foreign keys enabled via event listener
- Created 10 SQLAlchemy models: Organization, Team, Member, Workflow, WorkflowStep, TouchTimeConfig, DysfunctionConfig, Sprint, Issue
- Created TimestampMixin base class for id/created_at/updated_at (DRY)
- All models have proper relationships, unique constraints, and defaults per spec
- Issue model has self-referential blocked_by FK and multiple member FKs
- Set up Alembic with env.py, script.py.mako, and initial migration (001_initial_schema)
- Created Pydantic v2 schemas for all 9 entities (Base, Create, Read, Update variants)
- Wired models into FastAPI with lifespan event for table creation fallback
- Updated /health endpoint stage from "0" to "1"
- Added pydantic-settings dependency to pyproject.toml
- Added setuptools package discovery config (include app* only)
- Created .venv with Python 3.12 for local development
- 95 tests total, all passing

## [2026-03-15] Stage 0 — Infrastructure verification and CI/CD fix
### Changed
- Deployed .env to EC2 with all secrets (Jira, OpenAI, app config), chmod 600
- Configured GitHub repository secrets (EC2_HOST, EC2_USER, SSH_PRIVATE_KEY) via API
- Fixed deploy workflow: added git safe.directory and sudo for docker compose
- Fixed /app/jira-simulator ownership to ec2-user (was root from user-data)
- Fixed /data ownership to ec2-user
- Updated Terraform user-data to set correct ownership on future instances
- Verified full CI/CD pipeline end-to-end: tests pass, deploy succeeds, containers rebuilt
- Updated agent_instruction.md with full handoff context for Stage 1
### Fixed
- CI/CD deploy failure: "dubious ownership" git error on EC2
- CI/CD deploy failure: .env permission denied (owned by root, deploy runs as ec2-user)

## [2026-03-15] Stage 0 — Terraform apply and EC2 verification
### Changed
- Terraform applied: 11 AWS resources created (EC2, EBS, EIP, SG, IAM, DLM)
- EC2 root volume increased from 20GB to 30GB (Amazon Linux 2023 AMI minimum)
- User data script updated: added Docker Buildx v0.19.3 install (bundled version too old)
- User data script updated: added Node.js 20 install and frontend build step
- Frontend package-lock.json added to repo
### Fixed
- Docker compose build failure due to outdated buildx (< 0.17.0 bundled with Amazon Linux)
- Frontend 403 error: added frontend build step to user data script

## [2026-03-15] Stage 0 — Initial project skeleton and infrastructure code
### Changed
- Created GitHub repo at https://github.com/mrscrum/jira-simulator
- Full directory skeleton per AGENTS.md repository structure
- Terraform code: EC2 (t3.small, Amazon Linux 2023), EBS (20GB gp3 encrypted), DLM snapshots (daily, 7-day retention), Elastic IP, Security Group (22/80/443), IAM roles
- Docker Compose: backend (FastAPI) + nginx (reverse proxy), plus dev overrides
- Nginx config: static files, /api/* proxy, /health endpoint
- GitHub Actions CI/CD: test → lint → deploy pipeline
- Backend scaffold: FastAPI /health endpoint returning {"status":"ok","stage":"0"}, one passing test
- Frontend scaffold: Vite + React + TypeScript placeholder, one passing test
- Documentation: README, .env.example, agent_instruction.md, all backlog stage files
- Installed obra/superpowers TDD skill and clean-code-skills at project level

## [2026-03-15] Stage 0 — Swap LLM provider from Anthropic to OpenAI
### Changed
- Replaced all Anthropic/Claude references with OpenAI across AGENTS.md, stage-0-prompt.md, and cc-initiate-project.md
- Environment variable `ANTHROPIC_API_KEY` renamed to `OPENAI_API_KEY` in all spec files
- httpx description updated from "Claude API calls" to "OpenAI API calls" in AGENTS.md
- README prerequisites updated from "Anthropic API key" to "OpenAI API key" in stage-0-prompt.md

## [2026-08-10] Stage 7 — Current implementation assessment
### Changed
- Added `docs/requirements-functionality-map.md` with the current product boundary, architecture,
  implemented/partial/missing functionality, verification evidence, and prioritized risks.
- Updated `README.md`, `agent_instruction.md`, and Stage 7 backlog tracking to reflect the assessed
  code rather than historical stage claims.
### Fixed
- No fixes made; this task was strictly assessment and documentation.

## [2026-08-10] V2 Stage 0 — Approved durable implementation plan
### Changed
- Added the authoritative `docs/v2/` requirements, decisions, architecture, contracts, operations,
  implementation runbook, context-sized task plan, and verification matrix.
- Added the active `backlog/v2/` namespace with stable task IDs, dependencies, gates, UAT states,
  and the next execution pointer.
- Added Jira-side human intervention as a first-class bidirectional integration requirement covering
  sprint lifecycle, scope, unknown cards, re-estimation, status/field changes, echo suppression, and
  isolated conflict handling.
- Added executable starter timing/risk catalogs, an exact cross-process RNG contract, proficiency
  mechanics, restart re-anchoring, protected Jira webhook/poll reconciliation, and staged Codex/MCP
  delivery contracts so implementation does not require silent product choices.
- Split oversized Jira-intervention, Codex-control, persistence, ground-truth, and release tasks; the
  five-Scrum-team production gate now precedes Kanban, with a later mixed-team regression.
- Added authority/quarantine pointers so fresh agents do not execute obsolete v1 handoff, Stage 4,
  distribution, carryover-penalty, precompute, or comment plans.
- Updated the current-state README and agent handoff without claiming v2 implementation.
- Incorporated Pavel's explicit requirement that managed projects survive manual Jira sprint and
  card intervention, including webhook/poll ingestion, human-wins fields, protected topology,
  restart ordering, and stale-outbox supersession.
- Completed the recommended Scrum/Kanban starter contracts, exact replay/event-time/availability
  algorithms, public-API Jira topology strategy and early tenant gate, safe ambiguous-create/outbox
  lease semantics, private API/dashboard authentication, and retrievable deterministic calibration
  exports.
- Added `V2-S0-T09`, bringing the executable plan/backlog to 96 matching context-sized tasks, and
  added the required documentation-task evidence record.
### Fixed
- Resolved the planning conflicts around database, workflow ownership, runtime mode, sprint
  boundaries/carryover, Jira identity/comments, Codex/OpenAI separation, and ground-truth exposure.
- Resolved remaining contradictions in route topology, successor full-scope projection, paused
  commands, in-flight sync freeze, Stage 3 auth ordering, and ground-truth download parity.
- No implementation code or runtime behavior was changed.

## [2026-08-10] V2 Stage 0 — Simplify active plan
### Changed
- Added `docs/v2/high-level-plan.md` as the concise active requirements, architecture, roadmap, and
  MVP acceptance document.
- Replaced the active 96-task pointer with seven outcome milestones and marked the detailed planning
  artifacts as optional reference.
- Kept direct Jira sprint/card intervention and restart reconciliation explicit in the active scope.
### Fixed
- Removed implementation-level algorithms, schemas, and task sequencing from the mandatory plan so
  the implementing model can make appropriate local design choices.
- No application code or runtime behavior was changed.

## [2026-08-10] M1 — Persist isolated team runtime shell
### Changed
- Added isolated v2 Scrum blueprint persistence, canonical helpers, aware-UTC storage, and atomic team creation.
- Added Alembic revision 013 with four additive v2 tables and a complete downgrade.
- Added v2 tests and RED/GREEN/full-suite/Ruff/Alembic evidence.
### Fixed
- No v1 behavior changed; v2 model registration is additive only.

## [2026-08-10] M1 — Task 1 review fix round 1
### Changed
- Replaced mutable blueprint dictionaries with deep typed/frozen models and cross-field validation.
- Strengthened restart, final SQL INSERT rollback, v1 invisibility, and populated migration round-trip tests.
- Updated current-state counts and retained exact fix-round verification evidence.
### Fixed
- Rejects nested extras, non-UTC blueprint instants, incomplete timing/risk materialization, invalid
  workflow references, unsupported activities, unordered timing anchors, and overlapping availability.

## [2026-08-10] M1 — Task 1 review fix round 2
### Changed
- Normalize every aware blueprint boundary and availability instant to UTC in the typed snapshot.
- Preserve the validated canonical input document and its SHA-256 identity across normalization.
- Added exact focused/full/Ruff/Alembic/function-length command evidence for the review fix.
### Fixed
- Valid aware blueprint instants with non-zero UTC offsets are no longer rejected.

## [2026-08-10] M1 — Task 1 review fix round 3
### Changed
- Replaced mutable private canonical state with a frozen excluded model field.
- Enabled strict JSON-mode validation throughout the resolved blueprint hierarchy.
- Added canonical immutability/hash and scalar wire-type regression coverage.
### Fixed
- Canonical blueprint bytes can no longer be reassigned independently of typed state.
- Numeric, string, and boolean scalar substitutions are no longer silently coerced.

## [2026-08-10] V2 Stage 0 — Add independent implementation prompt
### Changed
- Added a ready-to-paste v2 implementation prompt with direct links to the active requirements,
  current assessment, milestone backlog, repository rules, and handoff.
- Authorized routine local decisions and continued work across intermediate milestones while
  preserving UAT, deployment, remote push, and live Jira mutation as explicit external gates.
- Defined implementation priorities, TDD expectations, verification, and the required morning
  handoff without reintroducing a low-level task plan.
### Fixed
- Prevented missing credentials or one blocked integration path from stopping unrelated local work.
- No application code or runtime behavior was changed.

## [2026-08-10] M1 — Commit live slices atomically
### Changed
- Added immutable activity, ground-truth, projection-intent, runtime-advance, commit, and cursor-page
  contracts with deterministic UUIDv5 identities, canonical payload hashes, and aware-UTC times.
- Added a compare-and-swap v2 unit of work that advances one runtime and appends three ordered
  ledgers in one transaction, with deterministic replay, conflict rollback, and stable pagination.
- Added Alembic revision 014 with explicit runtime version backfill, three append-oriented v2
  tables, and a complete independent downgrade to revision 013.
- Added RED/GREEN, failure-injection, stale-writer, restart, projection-boundary, and populated
  migration round-trip evidence without contacting Jira or OpenAI.
### Fixed
- Kept projection delivery outside the authoritative transaction so a post-commit adapter failure
  cannot undo runtime, activity, evidence, or pending intent state.
- Added fresh-process Alembic/public-import regressions, lazy persistence exports, and cycle-aware
  additive v2 model registration so commands cannot enter an `app.models`/v2 mapping import cycle.

## [2026-08-10] M1 — Task 2 review fix round 1
### Changed
- Added strict public draft revalidation, deep payload immutability, pre-session UOW validation,
  and deterministic semantic-key race coverage for all three v2 ledgers.
- Made every public v2 model/UOW cold-import order register and create all seven v2 tables.
- Strengthened post-commit adapter-failure evidence to reload ground truth and added a supplemental
  Task-1-base proof that the committed revision-014 migration test fails when migration 014 is absent.
### Fixed
- Identical semantic insert races now resolve to the committed winner without duplicate rows;
  conflicting races raise `SemanticDeduplicationConflict` and roll back the whole proposed slice.
- Direct constructors and `dataclasses.replace` can no longer bypass semantic UUID, canonical
  JSON/digest, identifier/type, version, projection-status, or aware-instant invariants.
- Draft payload aliases can no longer mutate the canonical snapshot through `|=`.

## [2026-08-10] M1 — Task 2 review fix round 2
### Changed
- Added exhaustive top-level and nested strict-JSON key regressions for `DraftEnvelope`, all three
  live-slice draft factories, and the pre-session persistence boundary.
### Fixed
- Integer, boolean, `None`, mixed, and recursively nested non-string object keys are now rejected
  before `json.dumps` can coerce them into different canonical JSON identities.

## [2026-08-10] M1 — Add deterministic decision sampling
### Changed
- Added the exact closed `HMAC_SHA256_U53_V1` decision contract, immutable draw provenance, and
  eight fixed-namespace semantic UUIDv5 identity helpers without persistence or mutable RNG state.
- Added pure bounded full-dwell and touch-work samplers with exact endpoints, validated finite
  inputs, log1p-space dwell interpolation, and immutable sample provenance.
- Added independent literal HMAC vectors, cross-process/order replay tests, starter timing-cell
  coverage, pure-domain architecture checks, and complete local verification evidence.
### Fixed
- Deterministic v2 decisions no longer require a future caller to invent process-local RNG state,
  database ordering, or implicit occurrence consumption.

## [2026-08-11] M1 — Bind deterministic sample provenance
### Changed
- Sealed `UniformDraw` creation behind the keyed deterministic stream and made direct construction
  plus `dataclasses.replace` reject instead of accepting unauthenticated provenance.
- Restricted current decision entities to semantic UUIDs, enforced every documented zero/nonzero
  occurrence scope, and bounded all semantic indices to the exact safe-integer domain.
- Added independently re-encoded cancellation and maximum-safe-integer ECMAScript vectors plus
  table coverage for every decision type.
### Fixed
- Arbitrary digests with self-consistent derived U53 values can no longer form valid draws.
- Boolean canonical coordinates no longer compare equal to integer coordinates.
- `DurationSample` construction and replacement now reject in-bounds results that do not equal the
  retained dwell/touch formula.

## [2026-08-11] M1 — Seal deterministic value objects
### Changed
- Made every Task 3 provenance and sampling dataclass frozen and slotted with no instance mapping.
- Made shallow/deep copying preserve immutable identity and made pickle/reduce reconstruction reject
  for decision coordinates, streams, draws, duration parameters, and duration samples.
- Added direct mapping, ordinary attribute, copy, reduction, and injected pickle-state regressions.
### Fixed
- Instance-dictionary mutation and unvalidated pickle state can no longer alter root seeds,
  decisions, digests, unit values, duration parameters, or sampled results.

## [2026-08-11] M1 — Add dual-clock business calendar
### Changed
- Added pure immutable UTC/business-time intervals, elapsed clocks, forward business-duration
  addition, working-date helpers, and fixed local cadence derived from resolved team calendars.
- Added explicit UTC-round-trip validation for nonexistent and ambiguous IANA local boundaries,
  including spring-forward and fall-back coverage without reading host-local timezone state.
- Added exact `US_FEDERAL_V1` observed-holiday materialization and idempotent bounded-horizon
  extension, plus focused/regression/full/Ruff/Alembic/shape evidence.
### Fixed
- Fixed sprint cadence is now represented separately from working-calendar adjustment, so weekends,
  holidays, and DST changes cannot shift the original local boundary clock.
- No persistence, schema, scheduler, engine, v1, Jira/OpenAI, frontend, or deployment behavior was
  changed.
