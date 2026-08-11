# Jira Team Simulator v2 — Operations Plan

> **OPTIONAL REFERENCE.** The active operational outcomes are in
> [`high-level-plan.md`](high-level-plan.md); exact limits and mechanisms can be chosen during the
> relevant milestone.

This is the target operational contract. It does not describe currently implemented behavior until
the corresponding backlog tasks are complete.

## Runtime Ownership

- Run one application replica and one APScheduler owner.
- Each team runtime row carries state, version, cursor, next wake, and bounded ownership lease.
- A tick commits only if the loaded runtime version/lease still matches.
- Scheduler startup automatically loads active v2 teams; no global start request is required.
- V1 and v2 scheduler jobs are explicitly separated by runtime version.
- MVP defaults are a five-minute team tick and five-minute Jira reconciliation poll. A normal tick
  credits at most one configured interval and advances its cursor to the wake instant; delayed or
  restart-overdue intervals outside that bound are discarded, not queued for catch-up.

## Team Controls

| Control | Internal simulation | New Jira intents | Committed Jira outbox | Inbox/reconciliation |
|---|---|---|---|---|
| Running | Advances | Created | Drains | Runs |
| Team paused | Frozen; explicit team commands persist as held | None until resume | Drains | Observes and applies supported human changes with zero time credit |
| Sync frozen | Advances | Created | Does not drain | Applies supported human changes; records conflicts |
| Projection backpressured | Frozen | None | Drains/retries when Jira permits | Observes and reconciles |
| Team paused + sync frozen | Frozen; explicit team commands persist as held | None until resume | Does not drain | Applies supported human changes with zero time credit |
| Inactive/provisioning/ready-not-started | Frozen | Provisioning only until ready | Drains committed/provisioning commands unless sync-frozen | Applies supported human changes with zero time credit |

Pause/resume/freeze commands return only after the persisted runtime version changes. A stale tick
cannot commit against the old version: pause increments a per-team `control_epoch`, and every tick
commit compares the epoch loaded under the same per-team mutex/writer fence.

Apart from runtime/sync controls and Jira-inbox adoption, a mechanics-changing command accepted or
becoming due while paused is durable but cannot apply: it consumes no domain RNG, changes no work
state, and creates no Jira intent. Mark it held with its original `effective_at`. The first running
transaction after resume processes held/due commands in
`(effective_at, accepted_at, persisted acceptance_sequence)` order after required Jira/lifecycle
reconciliation. The acceptance sequence is allocated with the command audit row and preserves
supplied input order for replay. Mechanics use the application instant, not the missed due instant,
and record `effective_at`, `applied_at`, and lateness. Revalidate the target/version then; a stale
command terminates with the contracted structured result and no partial effect. An absolute
availability interval that has already ended is recorded as applied with no current capacity effect.
Resume first advances the ordinary cursor to the resume instant with zero work/timer credit. If a
fixed sprint boundary passed while paused, run the same one-boundary reconciliation used after
restart before held commands; never feed the paused interval to `EVENT_TIME_LOOP_V1`.

Each team also has projection mode `DISABLED`, `FAKE`, or `JIRA_READY`. Jira-free fixtures may run in
the first two modes. A provisioned live team cannot start or emit live Jira intents until required
mappings/readiness are complete.

Sync freeze is outbound-only: it never disables webhook/poll ingestion or adoption of a supported
human Jira change. “Inactive” is not an archive/delete state (neither exists in MVP). During
provisioning, only saga-owned provisioning intents may be created; once ready but not started, no
new domain intent is created, while every already committed command drains unless an explicit sync
freeze or startup reconciliation barrier applies.

A requested sync freeze atomically increments the team delivery epoch and enters `FREEZING`, so no
new outbox claim can start. A request already in flight may settle only through its matching lease
token/epoch rule and cannot trigger another claim. When no active lease remains, the state becomes
`FROZEN`; if that is not immediate, the control returns an operation to poll. A late result is
evidence for reconciliation and cannot overwrite a newer command state.

## Availability and Timer Operation

- Natural dependency and absence remainders use the simulation-business-time representation in
  `architecture.md`. Only committed running tick slices decrement them; team pause, process downtime,
  and non-working time do not.
- Configured blueprint/settings intervals and command-created absolute runtime overlays remain UTC
  external truth while a team or process is paused. At resume/restart, resolve only intervals active
  at the current instant. Record an interval that started or ended while inactive, but create no
  backdated capacity, release, return, or work.
- Independent runtime overlays may overlap across sources. Runtime allocation resolves the minimum
  configured/runtime fraction and the minimum configured/runtime `daily_capacity_hours_override`,
  never mutates one source because another starts, and records the complete composition.
- A natural absence of `N` working-day equivalents starts with
  `N * nominal_workday_business_seconds`; persist and decrement the exact residual business seconds,
  so a crash or pause during a workday neither rounds nor consumes the unfinished portion.

## Restart Without Catch-Up

On process startup:

1. Open SQLite, enable/check WAL, foreign keys, busy timeout, and integrity prerequisites.
2. Complete Alembic migration or fail startup; never continue after migration failure.
3. Recover outbox commands left `IN_FLIGHT` into an unknown-outcome reconciliation state without
   delivering them yet.
4. Load active/paused/frozen runtime state and each Jira poll high-water mark.
5. Poll/read back Jira and apply relevant supported intervention inbox entries before any boundary
   reconciliation or outbox delivery.
6. Preserve the last committed work/content/event cursor and grant no downtime progress.
7. For an already-past fixed policy boundary not superseded by Jira, reconcile one active sprint,
   record skipped cadence windows, and create one successor in the current cadence window.
8. Set the ordinary cursor/next wake from the resume instant and discard ordinary overdue tick
   intervals; do not synthesize missed work, transcripts, risks, or empty sprints.
9. For a running team, apply durable commands that became due during downtime once in the first
   eligible transaction at the resume instant, with lateness and no backdated mechanics. Keep them
   held if the team itself remains paused.
10. Resume future ticks, then reconcile/drain committed outbox work at configured wall-clock pacing.

For a `JIRA_READY` team, failure of the initial poll enters visible `RECONCILIATION_PENDING` and
fences that team's ticks/outbox until the poll succeeds; retries continue and other teams are not
blocked. This is a startup safety barrier, distinct from an outage detected after a reconciled team
is already running.

## Jira Outage and Recovery

- Default outbound pacing is one Jira request per second per Jira instance with one in-flight request
  at a time; `Retry-After` always overrides this ceiling. The value is configurable and recorded.
- Default safety limits are 2,000 pending commands per team and 7,500 globally, with recovery low
  water at 50% of the applicable high-water mark.
- Depth uses the exact nonterminal states in `contracts/jira-operations.md`. At tick commit, calculate
  current depth plus the proposed atomic batch. If existing depth is already at a limit, no tick may
  begin. A batch that would exceed a limit is rolled back and only the backpressure control change
  commits; a batch that lands exactly on the limit commits with `PROJECTION_BACKPRESSURED` in the
  same transaction. Per-team pressure fences that team. Global pressure fences new tick/provisioning
  intents for every `JIRA_READY` team and rejects new provisioning acceptance, while all existing
  eligible outbox/provisioning work continues to drain.
- Internal simulation may continue while Jira is offline until a configurable per-team/global outbox
  safety limit is reached. At the limit, atomically enter `PROJECTION_BACKPRESSURED`, fence new team
  ticks/intents, and alert; do not discard intents or stop eligible outbox draining. After Jira
  recovers, an operator clears backpressure only after reconciliation and queue depth fall below the
  low-water mark.
- Respect `Retry-After`; otherwise use bounded exponential backoff with jitter.
- After recovery, reconcile unknown create/update outcomes before retrying.
- Drain at configured pacing and interleave read-back checks.
- Webhook loss is recovered by periodic changelog/state polling.
- A manual Jira change observed during outage is ordered by Jira observed/changelog time and applied
  through the intervention inbox before a conflicting pending projection is delivered.

## Manual Intervention Conflicts

- Supported human changes are accepted and displayed with actor, observed time, and result.
- Protected-field or unmapped changes isolate one item when possible.
- Impossible sprint topology pauses autonomous lifecycle for that team, while item observation and
  other teams continue.
- The dashboard and MCP state response provide server-generated resolution options; clients cannot
  submit arbitrary corrective payloads.
- No reconciliation silently deletes history or Jira resources.

## Content Failure

- Mechanics insert content jobs and never wait for them.
- Retry once for transient/validation failure, then persist a marked deterministic fallback.
- A missing/revoked OpenAI key produces fallback and an operational alert, not a failed tick.
- Enforce the approved server-side model profile plus bounded input/output token limits, timeout,
  retries, and maximum jobs per worker cycle. MVP defaults are 1,200 output tokens, 45 seconds, one
  retry, and five claimed jobs per cycle.

## Storage, Backup, and Restore

- Database path: `/data/simulator.db` on encrypted EBS.
- Back up with a SQLite-safe online backup/checkpoint procedure; copying a live WAL database without
  its WAL/SHM files is not an accepted backup.
- Retain existing EBS/DLM snapshots and add application-level restore evidence.
- Before migration/deployment, create a timestamped backup and verify `PRAGMA quick_check`.
- Restore drills use a new disposable path, run migrations, boot the app with external delivery
  disabled, and compare state/event/outbox counts/checksums before enabling Jira.

## Deployment

1. CI runs backend, Ruff, frontend tests/build, contract/schema checks, and migration round-trip.
2. Create/verify backup.
3. Deploy one replica with v2 scheduler disabled for schema/health smoke.
4. Verify migration, database path, health, auth, and Jira discovery.
5. Enable v2 scheduler for designated teams only.
6. Observe at least one tick/outbox/inbox/reconciliation cycle.
7. Roll back application image if health fails; preserve additive v2 tables and Jira resources.

Production promotion and each stage UAT require Pavel's sign-off under `/AGENTS.md`.

## Minimum Diagnostics

- scheduler owner, team next wake, cursor, version, tick duration and lag;
- SQLite WAL size, busy retries, transaction duration, integrity result and database size;
- outbox depth/age/status/attempt/rate, inbox depth/age/classification and reconciliation state;
- Jira health, 429/5xx/timeout counts and read-back divergence;
- active risks, dependencies, member availability and quarantined items;
- content jobs, fallbacks, latency and token usage when available;
- transcript/ground-truth volume and export status; and
- authentication failures and mutation audit correlation IDs.

## Emergency Procedures

- **Unexpected Jira writes:** sync-freeze the affected team, preserve outbox, inspect correlation and
  field ownership, then use explicit reconciliation. Do not delete queue rows.
- **Wrong internal transitions:** pause the team, export state/ground truth, preserve evidence, and
  stop before corrective mutation.
- **Database integrity failure:** stop scheduler/writer, preserve database/WAL/SHM, restore the latest
  verified backup to a new path, and do not overwrite the original.
- **Runaway content cost:** disable content worker, not simulation; fallback continues.
- **Manual Jira conflict storm:** pause lifecycle or quarantine affected items, keep polling evidence,
  and avoid overwriting human changes.
