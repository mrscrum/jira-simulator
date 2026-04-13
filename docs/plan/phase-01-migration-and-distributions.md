# Phase 1: Database Migration + Distribution Module

## Context

This is the first phase of the simulation engine rewrite. It creates the database foundation and the pure-math distribution sampling module that all subsequent phases depend on.

Full requirements: `docs/simulation-engine-rewrite-requirements.md`

---

## 1a. Create Alembic Migration

**File:** `backend/alembic/versions/009_engine_rewrite.py`

### teams table — add columns:
- `sprint_capacity_min` (Integer, nullable=False, server_default="20")
- `sprint_capacity_max` (Integer, nullable=False, server_default="40")
- `priority_randomization` (Boolean, nullable=False, server_default="0")
- `first_sprint_start_date` (DateTime, nullable=True)
- `tick_duration_hours` (Float, nullable=False, server_default="1.0")

### issues table — add columns:
- `sampled_full_time` (Float, nullable=False, server_default="0.0")
- `sampled_work_time` (Float, nullable=False, server_default="0.0")
- `elapsed_full_time` (Float, nullable=False, server_default="0.0")
- `elapsed_work_time` (Float, nullable=False, server_default="0.0")
- `work_started` (Boolean, nullable=False, server_default="0")

### sprints table — add column:
- `capacity_target` (Integer, nullable=True)

### touch_time_configs table — add columns:
- `full_time_p25` (Float, nullable=True)
- `full_time_p50` (Float, nullable=True)
- `full_time_p99` (Float, nullable=True)

### workflow_steps table — add column:
- `roles_json` (String, nullable=True) — JSON array of role names; when set, overrides `role_required`

### move_left_config table — add column:
- `issue_type` (String, nullable=True) — makes move-left per-item-type; NULL = applies to all types

### members table:
- Update all existing rows: set `max_concurrent_wip = 1`

### Sprint phase cleanup:
- Update existing sprints: change phase "BACKLOG_PREP" → "PLANNING", "REVIEW" → "COMPLETED", "RETRO" → "COMPLETED"

---

## 1b. Create Distribution Sampling Module

**File:** `backend/app/engine/distributions.py`

Pure functions, zero DB dependency, fully testable in isolation.

### Functions:

```python
def fit_lognormal(p25: float, p50: float, p99: float) -> tuple[float, float]:
    """Fit log-normal distribution from three percentiles.

    mu = ln(p50)  (median of log-normal = exp(mu))
    sigma derived by averaging estimates from p25 and p99:
      sigma_from_p25 = (ln(p50) - ln(p25)) / 0.6745  (z-score for 25th percentile)
      sigma_from_p99 = (ln(p99) - ln(p50)) / 2.3263  (z-score for 99th percentile)
      sigma = (sigma_from_p25 + sigma_from_p99) / 2

    Returns (mu, sigma).
    """

def sample_full_time(p25: float, p50: float, p99: float, rng: random.Random) -> float:
    """Sample full-time-in-status from fitted log-normal. Returns hours (>= 0)."""

def sample_work_time(min_hours: float, max_hours: float, rng: random.Random) -> float:
    """Sample work-time-in-status from uniform[min, max]. Returns hours."""

def sample_sprint_capacity(min_sp: int, max_sp: int, rng: random.Random) -> int:
    """Sample sprint capacity target from uniform[min, max]. Returns story points."""
```

### Key constraints:
- `sample_full_time` must return >= some small epsilon (e.g., max(sample, 0.1))
- `sample_work_time` returns 0.0 if min=max=0 (queue/wait status)
- All functions accept `rng: random.Random` for reproducibility

---

## 1c. Tests

**File:** `backend/tests/unit/test_distributions.py`

Test cases:
- `fit_lognormal` returns correct mu/sigma for known inputs
- `sample_full_time` produces values in reasonable range for given percentiles
- `sample_work_time` returns values within [min, max]
- `sample_work_time(0, 0, rng)` returns 0.0
- `sample_sprint_capacity` returns int within [min, max]
- Reproducibility: same seed → same samples

---

## Existing files to reference:
- `backend/alembic/versions/008_stage4_schema.py` — latest migration, follow same patterns
- `backend/app/models/` — all model files to understand current column definitions
- `backend/app/engine/capacity.py` — existing pure-function pattern to follow

## Dependencies:
- None (this phase is independent)

## What comes next:
- Phase 2 (Model Updates) depends on this migration being complete
- Phase 5 (Workflow Engine) imports from `distributions.py`
