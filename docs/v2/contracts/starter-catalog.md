# V2 Starter Catalog Contract

This catalog removes implementation-time product choices when a request omits configuration. It
contains the first Scrum profile and the approved Kanban follow-on profile; neither is a claim of
learned calibration. Every preview names the catalog versions it resolved, shows generated values,
and lets the user change them before confirmation.

## Catalog identity and resolution

- Catalog: `SCRUM_BALANCED_V1`; immutable after release.
- Kanban catalog: `KANBAN_BALANCED_V1`; creation remains disabled until G6 but its defaults are
  immutable and previewable before then.
- Timing: `BALANCED_DWELL_TOUCH_V1`; algorithm `SCALED_ANCHOR_GRID_V1`.
- Risk: `BALANCED_CAUSAL_RISK_V1`; algorithm `LOGISTIC_RISK_V1`.
- Workflow: `SCRUM_CANONICAL_ROUTE_V1`.
- Jira topology: `OFFICIAL_PROJECT_SCOPED_V1`; project → dedicated issue-type scheme → canonical
  workflow scheme → board, using documented public APIs and exact board-configuration read-back.
- Content: `INTERNAL_CONTENT_DEFAULT_V1`.
- If a future catalog changes any number or route, create a new version; never edit persisted v1
  values.
- A v1 template may be imported only into a new explicit catalog version after producing full v2
  anchor coverage and provenance. The old approximate fit and 25% carryover penalty are never
  inherited.

## Recommended team and backlog defaults

- Locale/timezone: `en-US` and `America/Los_Angeles` when omitted.
- Calendar: Monday–Friday, 09:00–17:00 local, `US_FEDERAL_V1`, 14 local-calendar-day Scrum cadence,
  and a 35–45 point capacity range.
- Seed: when omitted, the Codex skill draws 32 bytes from its operating-system CSPRNG, encodes them
  as 64 lower-case hexadecimal characters, and places that value in the draft before preview. The
  server never silently replaces it.
- First sprint start: the earliest nonholiday working-date 09:00 local boundary at least 48 hours
  after the draft's generation instant. Persist the resolved RFC 3339 instant with its numeric UTC
  offset. Preview tokens expire after 24 hours, so a confirmed default boundary remains future.
- Holiday materialization: include observed US federal dates from January 1 of the year before the
  first start through December 31 ten years after its year; persist that final date as
  `holiday_horizon_end`. `US_FEDERAL_V1` contains New Year's Day, MLK Day (third Monday in January),
  Washington's Birthday (third Monday in February), Memorial Day (last Monday in May), Juneteenth,
  Independence Day, Labor Day (first Monday in September), Columbus Day (second Monday in October),
  Veterans Day, Thanksgiving (fourth Thursday in November), and Christmas. A fixed-date Saturday
  is observed Friday and a Sunday Monday; Inauguration Day is excluded. When fewer than two complete
  local calendar years remain, the calendar service appends another ten years using the same frozen
  rule version and records a new calendar-policy/ground-truth revision.
- Role mix: one product owner, one analyst, three developers (at least two eligible for code review),
  two QA members, and one Scrum facilitator. A person may cover multiple responsibilities. Codex
  supplies synthetic names and shows them in preview.
- Member defaults: 6 labor hours per working day, WIP limit 2, availability fraction 1.0, and the
  exact responsibility proficiencies below unless the request establishes a different profile.
- Scrum archetype: `Platform product team`.

The default Scrum member slots and responsibility profiles are exact catalog values. Codex may
replace the example names with synthetic names, but it preserves the slot count, roles, activities,
and proficiency values unless the user changes them in the preview.

| Slot | Role | Responsibility profile (`activity`: proficiency) |
|---|---|---|
| Product owner | Product Owner | `product_acceptance`: `1.10`; `analysis`: `0.80` |
| Analyst | Business Analyst | `analysis`: `1.15` |
| Developer 1 | Software Engineer | `development`: `1.10`; `code_review`: `1.00` |
| Developer 2 | Software Engineer | `development`: `1.00`; `code_review`: `1.10` |
| Developer 3 | Software Engineer | `development`: `0.95`; `code_review`: `0.90` |
| QA 1 | Quality Engineer | `quality_assurance`: `1.10` |
| QA 2 | Quality Engineer | `quality_assurance`: `0.95` |
| Scrum facilitator | Scrum Facilitator | `analysis`: `0.75` |

`scrum_facilitation` is a team role, not a canonical workflow activity, and is not emitted as a
member responsibility. With `availability: []`, a member is fully available (`1.0`) on every team
working date and uses `daily_capacity_hours` as the pre-fraction daily labor cap. Within the single
active, non-overlapping configured interval, `daily_capacity_hours_override` replaces that baseline
cap when present and `availability_fraction` limits it:

`configured_daily_labor_cap = (daily_capacity_hours_override ?? daily_capacity_hours) * availability_fraction`.

Risk- or command-created runtime availability overlays are stored separately from the confirmed
blueprint and may only restrict configured availability. At an instant, take the minimum of the
configured fraction and all active runtime fractions, and the minimum of the configured
pre-fraction cap and all active runtime cap overrides; absent runtime values contribute no further
limit. Their product is the effective daily labor cap. Thus the starter `MEMBER_UNAVAILABLE`
overlay, whose fraction is `0`, always yields zero labor without erasing the member's baseline or
planned interval. Increasing availability requires a versioned team-settings change, not a runtime
overlay.

- Backlog target: 40 items.
- Issue-type weights: Story `.65`, Bug `.15`, Task `.12`, Spike `.04`, Enabler `.04`.
- Story-point weights: 1 `.10`, 2 `.15`, 3 `.30`, 5 `.25`, 8 `.15`, 13 `.05`.
- Priority weights: Highest `.05`, High `.20`, Medium `.50`, Low `.20`, Lowest `.05`.
- Manual Jira import defaults: Task and 3 story points.
- Backlog arrival pattern: `ON_DEMAND`; replenish to target during planning and after committed
  removal/completion events, never from a wall-clock Poisson process in the Scrum MVP.
- Initial factor sampling: description quality `0.35 + 0.60u`; latent complexity
  `0.10 + 0.80u`, each with its own deterministic decision key.

Weights are normalized by their positive sum. An all-zero/negative/non-finite map is invalid.
Weighted draws traverse these immutable orders and choose the first cumulative upper bound strictly
greater than `u` (the explicit `u=1` endpoint clamps to the last value): issue types Story, Bug,
Task, Spike, Enabler; points 1, 2, 3, 5, 8, 13; priorities Highest, High, Medium, Low, Lowest.

## Recommended content defaults

- Domain: the team/product domain produced in the confirmed blueprint.
- Generation enabled: true.
- Generated fields: backlog summary, acceptance criteria, sprint goal, and event narration.
- Model profile: `INTERNAL_CONTENT_DEFAULT_V1`. This is a server-side configuration reference, not
  a model name or API key; a missing or unresolved profile selects deterministic fallback.
- Worker limits: at most 5 jobs claimed per cycle, 45-second request timeout, 1 retry, and 1,200
  output tokens per job.
- Daily transcript: true. Jira comments: false.

Every override is previewed and persisted with its policy version. Enabling content for a running
team creates only safe backfill candidates under `R-CONTENT-001`; it never changes mechanics or
overwrites human-authored content.

## Canonical Scrum routes

`Blocked External` is an exceptional blocking episode and `Cancelled` is an exceptional terminal;
neither appears in an ordinary route. A route step has exactly one required activity for MVP; a
null activity means no touch capacity is needed.

| Key / Jira name | Category | Allowed activity | Consumes capacity | Pauses service clock |
|---|---|---|---:|---:|
| `TO_DO` / To Do | TODO | none | false | false |
| `ANALYSIS` / Analysis | IN_PROGRESS | analysis | true | false |
| `DEVELOPMENT` / Development | IN_PROGRESS | development | true | false |
| `CODE_REVIEW` / Code Review | IN_PROGRESS | code_review | true | false |
| `QA` / QA | IN_PROGRESS | quality_assurance | true | false |
| `PO_REVIEW` / PO Review | IN_PROGRESS | product_acceptance | true | false |
| `BLOCKED_EXTERNAL` / Blocked External | IN_PROGRESS | none | false | true |
| `DONE` / Done | DONE | none | false | false |
| `CANCELLED` / Cancelled | DONE | none | false | false |

| Type | Ordered `(status: activity)` route |
|---|---|
| Story | `TO_DO`: null → `ANALYSIS`: analysis → `DEVELOPMENT`: development → `CODE_REVIEW`: code_review → `QA`: quality_assurance → `PO_REVIEW`: product_acceptance → `DONE`: null |
| Bug | `TO_DO`: null → `DEVELOPMENT`: development → `CODE_REVIEW`: code_review → `QA`: quality_assurance → `DONE`: null |
| Task | `TO_DO`: null → `DEVELOPMENT`: development → `CODE_REVIEW`: code_review → `QA`: quality_assurance → `DONE`: null |
| Spike | `TO_DO`: null → `ANALYSIS`: analysis → `DEVELOPMENT`: development → `PO_REVIEW`: product_acceptance → `DONE`: null |
| Enabler | `TO_DO`: null → `ANALYSIS`: analysis → `DEVELOPMENT`: development → `CODE_REVIEW`: code_review → `QA`: quality_assurance → `DONE`: null |

## Timing grid

The base row is a three-point Story in business hours:

| Status | minimum | p25 | p50 | p99 | maximum | touch min | touch max |
|---|---:|---:|---:|---:|---:|---:|---:|
| `TO_DO` | 0.25 | 1 | 2 | 8 | 16 | 0 | 0 |
| `ANALYSIS` | 0.5 | 2 | 4 | 12 | 24 | 1 | 3 |
| `DEVELOPMENT` | 1 | 4 | 8 | 24 | 48 | 3 | 8 |
| `CODE_REVIEW` | 0.5 | 1.5 | 3 | 10 | 20 | 0.75 | 2.5 |
| `QA` | 0.5 | 2 | 4 | 14 | 28 | 1.5 | 4 |
| `PO_REVIEW` | 0.25 | 1 | 2 | 8 | 16 | 0.5 | 1.5 |
| `DONE` / `CANCELLED` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Materialize every active route-status × type × Fibonacci story-point cell by multiplying every
positive dwell/touch value by both factors below and rounding half-even to six decimal hours:

| Story points | 1 | 2 | 3 | 5 | 8 | 13 |
|---|---:|---:|---:|---:|---:|---:|
| Size factor | .50 | .75 | 1.00 | 1.35 | 1.80 | 2.40 |

| Type | Story | Bug | Task | Spike | Enabler |
|---|---:|---:|---:|---:|---:|
| Type factor | 1.00 | .85 | .90 | 1.15 | 1.10 |

Terminal zero rows remain zero. Semantic validation proves exactly one effective timing entry for
every active cell and rejects missing/duplicate cells or unordered anchors/touch bounds.

## Causal risk starter profile

The starter `enabled_risks` value is exactly, in catalog order,
`["EXTERNAL_DEPENDENCY", "CANCELLATION", "REVIEW_REJECTION", "MEMBER_UNAVAILABLE"]`.
All enabled logistic bases satisfy `0 < p0 < 1`; absence from `enabled_risks` disables evaluation.
Factors are clamped to `[0,1]`: `size` uses the size-factor value linearly normalized between `.50`
and `2.40`; `poor_description = 1 - quality`; complexity is stored directly; dependency is 0/1;
prior rework is `min(rework_count / 3, 1)`; member utilization and WIP ratio use their configured
capacity denominators. The probability formula is in `architecture.md`.

| Risk / trigger / occurrence key | Base | Coefficients | Clamp | Mechanical policy |
|---|---:|---|---|---|
| External dependency / first entry to a touch status / visit ID | .04 | size `.60`, poor description `.35`, complexity `.80`, prior rework `.20` | `.005–.35` | Pause the normal visit for a uniformly sampled 8–40 business hours; release worker capacity. |
| Cancellation / first working-day boundary per active item / item + business date | .01 | size `.20`, poor description `.25`, complexity `.25`, dependency `.70` | `.001–.12` | Enter terminal Cancelled and release capacity. |
| Review rejection / attempted normal exit from Code Review, QA, or PO Review / visit ID | .12 | size `.35`, poor description `1.30`, complexity `1.00`, prior rework `.30` | `.02–.75` | Use the exact rejection map/cap/formula below. |
| Member unavailable / first workday boundary per available member / member + business date | .01 | utilization `.50`, WIP ratio `.50` | `.001–.10` | Availability fraction 0 for a uniformly sampled 1–3 working days; release affected visit ownership. |

### Trigger snapshots and precedence

| Trigger | Immutable factor snapshot | Same-instant behavior |
|---|---|---|
| First entry to a positive-touch ordinary visit | Persisted size/quality/complexity/prior-rework values after the visit opens and before labor allocation. | Evaluate external dependency once for the visit; if true, open the block before any labor credit. |
| Local workday start | After due explicit commands and timer/availability returns, but before the new-day ledger reset or work credit, snapshot every eligible item/member in one batch. `dependency` is the then-active block flag. Member utilization is prior completed workday labor divided by prior scheduled available labor (0 when the denominator is 0); WIP ratio is active owned visits divided by member WIP limit. Clamp both to `[0,1]`. | Evaluate all cancellation decisions by item semantic UUID, then all unavailability decisions by member semantic UUID, from the unchanged batch snapshot. Apply cancellations then absences; one outcome cannot alter another decision's factors. |
| Attempted normal exit from Code Review, QA, or PO Review | Persisted item factors and rework count immediately before the attempted exit. | Evaluate rejection before closing/forward transition; rejection wins and creates the configured return visit. |

An eligibility/occurrence key is consumed only when its natural evaluation commits. A disabled risk,
ineligible entity, duplicate boundary/visit, forced command, or rolled-back transaction consumes
nothing. Timer resolutions at the same instant occur before the boundary snapshot; ordinary work at
that instant occurs after all boundary outcomes.

`STATUS_STAY_WARNING` is a monitor at dwell p50 and `LONG_STAY_DETECTED` is a monitor at p99 by
default; neither is a logistic risk. Carryover is derived only at a fixed or accepted manual sprint
boundary. Agent commands may causally induce those outcomes, but may not insert either outcome flag.

Duration draws and forced commands use separate deterministic decision types. A forced command is
recorded as forced and does not consume or change the natural hazard occurrence sequence.
Natural dependency duration is continuous `8 + 32u` simulation business hours. Natural absence is
`1 + floor(3u)` whole simulation working days for generator `u < 1` (the explicit `u=1` endpoint
clamps to 3). At trigger, each working-day unit becomes the nominal local wall-clock length of the
configured daily work interval in simulation business seconds; the persisted remainder decrements
only through newly processed running business time, including exact partial-day consumption.

The starter rejection map is `CODE_REVIEW → DEVELOPMENT`, `QA → DEVELOPMENT`, and
`PO_REVIEW → ANALYSIS` (or `DEVELOPMENT` only for a type whose route has no Analysis step). The
semantic validator requires every source/target to occur on that issue-type route with the target
strictly earlier. The maximum is three rejection returns per item. A rejection creates a normally
sampled new target visit, then adds `f * ordinary_sampled_touch` where `f = 0.25 + 0.50u` from the
separate rework-duration draw; completed work on the rejected review remains historical. After the
cap, natural rejection is not evaluated and records `REWORK_CAP_REACHED`; a forced command is
rejected with `REWORK_CAP_REACHED` rather than silently changing the route.

## Recommended Kanban defaults

`KANBAN_BALANCED_V1` reuses the locale/timezone, calendar/holiday horizon, member/role mix,
workflow/routes, timing grid, backlog distributions/target 40, risk profile, content policy, and seed
resolution above. It changes `backlog.arrival_pattern` to `POISSON_BUSINESS_TIME` and has no Scrum
policy or sprint rows.

### Arrival and replenishment

- Arrival policy: shifted bounded exponential business time. For its dedicated occurrence draw,
  next interarrival hours are
  `min(40, 1 + (-ln(1-u) * 7))`; generator `u < 1`, while the explicit endpoint `u=1` clamps to 40.
  The timer is initialized at committed team start, advances only over newly processed business
  time, and freezes through pause/restart downtime.
- One stochastic item arrives per due timer and uses the shared type/points/priority distributions.
  Class of service uses the ordered weights below. If the backlog already has 40 items, record
  `ARRIVAL_SUPPRESSED_BACKLOG_FULL`, sample the next interval, and do not accumulate a future burst.
- `ON_DEMAND` (when explicitly selected) refills to target immediately after a committed removal/
  completion. `SCHEDULED_BATCH` uses its configured working weekdays/local time/batch size; a missed
  downtime batch is skipped and the next future occurrence is scheduled. In every branch,
  `backlog.arrival_pattern` must equal `kanban.arrival_policy.kind`.
- Agent/Jira emerging items are explicit commands/interventions, do not consume a natural arrival
  occurrence, and enter the same ranked pull queue. Jira/manual items missing a class use
  `manual_import_default_class_key=STANDARD` with default provenance.

### Classes, WIP, pull, and service clocks

| Key | Name | Priority | Arrival weight | Start | Paused | Stop | Warning | Target business hours |
|---|---|---:|---:|---|---|---|---:|---:|
| `EXPEDITE` | Expedite | 1 | .10 | `TO_DO` | `BLOCKED_EXTERNAL` | `DONE`, `CANCELLED` | .50 | 16 |
| `FIXED_DATE` | Fixed Date | 2 | .10 | `TO_DO` | `BLOCKED_EXTERNAL` | `DONE`, `CANCELLED` | .75 | 40 |
| `STANDARD` | Standard | 3 | .75 | `TO_DO` | `BLOCKED_EXTERNAL` | `DONE`, `CANCELLED` | .75 | 80 |
| `INTANGIBLE` | Intangible | 4 | .05 | `TO_DO` | `BLOCKED_EXTERNAL` | `DONE`, `CANCELLED` | .75 | 120 |

- Status WIP limits: Analysis 3, Development 5, Code Review 3, QA 3, PO Review 2. To Do and terminal
  states are not WIP-limited. `Blocked External` is an overlay and counts against its suspended
  ordinary status limit, while member ownership/WIP capacity is released.
- Pull order is class priority, item priority, relative rank, then semantic item UUID. Expedite has
  no WIP bypass. Within `FIXED_DATE`, due instant sorts before item priority; a missing due instant is
  set to arrival plus that class's target business hours. Pull/transition occurs only when both destination-status WIP and the shared member
  allocator permit it; a full destination remains queued in the current status.
- The SLE clock starts on entry to To Do, pauses only for the configured blocker overlay, and stops
  on Done or Cancelled. Warning/breach fire once at exact business-time thresholds; calendar elapsed
  remains analytical. A manual move that skips the start begins the clock at the observed move with
  `MANUAL_START_STATUS_SKIPPED`; a move directly to a stop state records zero service time.
