# Jira Team Simulator v2 — Glossary

> **OPTIONAL REFERENCE.** Use this terminology where helpful; the active product contract is
> [`high-level-plan.md`](high-level-plan.md).

- **Activity event:** Human-readable operational projection of a committed fact. It is not the
  authoritative mechanical record.
- **Aggregate version:** Monotonic version used to reject stale writes for one team/item/sprint.
- **Business date:** Local calendar date in a team's timezone under its configured calendar.
- **Business time:** Time inside a team's configured working intervals excluding explicit holidays.
- **Calendar time:** Ordinary elapsed UTC duration including nights, weekends, and holidays.
- **Canonical status:** Stable simulator status key owned by a team and mapped 1:1 to a Jira status.
- **Carryover:** An unfinished Scrum item moved to the successor sprint at a planned or explicit
  human-overridden boundary. It retains status and remaining work without automatic penalty.
- **Content job:** Asynchronous request for prose based on already committed structured facts.
- **Dwell requirement:** Sampled business-time floor for one status visit.
- **External intervention:** A direct Jira human change normalized and applied as an attributed
  simulator command, or rejected/quarantined under the field policy.
- **Ground truth:** Immutable structured evidence containing inputs, algorithms, draws, causes,
  effects, versions, and Jira correlations for calibration.
- **Idempotency key:** Stable caller/operation key whose repeated use returns the same result and does
  not repeat a side effect.
- **Jira inbox:** Persistent deduplicated webhook/poll observations awaiting classification or
  application as manual interventions.
- **Jira outbox:** Persistent external intents inserted atomically with domain state and delivered
  after commit with dependency resolution.
- **Jira projection:** The Jira representation of committed simulator state. It may lag temporarily.
- **Latent complexity:** Persistent simulator-generated factor representing hidden implementation
  difficulty. It is not inferred by the content model.
- **Non-provisioning preview:** A validated, expiring audit/preview record that creates no team,
  Jira resource, simulation state, content job, or server-side OpenAI request.
- **Projection backpressure:** A safety state entered at outbox high water that fences new autonomous
  ticks/intents until reconciliation and operator-cleared low water.
- **Queue time:** Status-visit time with required touch work unable to progress because eligible
  capacity/WIP is unavailable. Both business and calendar forms are retained.
- **Quarantine:** Isolation of one invalid/unmapped item so it stops autonomous mutation while its
  state/evidence remain visible. It does not stop other items or teams.
- **Responsibility:** Activity/status work a virtual member is eligible to perform, with proficiency.
- **Risk decision:** Versioned probability calculation and deterministic draw that may produce an
  occurrence. A forced agent event is explicitly distinguished from a sampled occurrence.
- **Run:** One persisted simulation lineage for a team with a root seed and algorithm versions.
- **Service clock:** Kanban business-time SLA/SLE clock with configured start, pause, warning, target,
  and stop rules.
- **Simulation cursor:** End of the last committed interval for a team runtime.
- **Status visit:** One entry into a canonical status, with its own samples, progress, worker, clocks,
  causes, and exit reason. Re-entering a status creates a new visit.
- **Blocking episode:** An exceptional overlay that suspends an ordinary status visit, releases work
  capacity, records blocked duration, and resumes the same sample/progress without resampling.
- **Sync freeze:** Stops Jira outbox delivery for a team while internal simulation may continue.
- **Team pause:** Stops simulated time and new Jira intents for a team; explicit mechanics commands
  are held until resume, committed outbox may drain, and supported Jira observations still apply
  with zero time credit.
- **Topology strategy:** Versioned policy for provisioning a Jira project, issue types/schemes,
  workflow/statuses/scheme, fields/screens, and board in a capability-checked order.
- **Touch work:** Capacity-consuming active effort credited to an eligible virtual member.
- **Virtual identity:** Internal member identity projected only through `sim_assignee` and
  `sim_reporter`, never through simulated changes to Jira's actual assignee/reporter.
- **WIP:** Work in progress counted against a member or Kanban status limit under the active policy.
