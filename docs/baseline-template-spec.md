# Baseline Population Template — Requirements & Plan

## Overview

A **named template** system for auto-populating timing configurations when creating or updating projects (teams). The template captures cycle time distributions per issue type per size, and derives per-status work durations automatically.

---

## Requirements

### R1: Status Category on Workflow Steps
- Add a `status_category` field to `WorkflowStep` with values: `"todo"`, `"in_progress"`, `"done"`
- Persisted in DB, editable in the Workflow Designer UI
- Used by the template engine to determine which statuses receive cycle time distribution

### R2: Named Templates (CRUD)
- A **Template** is a named, reusable configuration stored in the DB
- Each template contains:
  - `name` (unique)
  - `description` (optional)
  - `spread_factor` (default 0.33) — controls work duration min/max derivation from median
  - A set of **TemplateEntry** rows, one per `(issue_type, story_points)`:
    - `issue_type: str`
    - `story_points: int`
    - Cycle time box plot inputs: `ct_min`, `ct_q1`, `ct_median`, `ct_q3`, `ct_max` (hours)
    - Derived outputs (computed, not stored): `p25 = ct_q1`, `p50 = ct_median`, `p99` derived from distribution shape

### R3: Cycle Time → Per-Status Distribution Logic
- **Cycle time** = total time across all `"in_progress"` statuses
- When applying a template to a team's workflow:
  1. Identify all workflow steps with `status_category = "in_progress"`
  2. For each `(issue_type, story_points)` template entry:
     - Distribute the cycle time across in-progress statuses
     - **Distribution strategy**: weight by status order position (earlier statuses get more time, reflecting typical "Development" > "Code Review" > "QA" pattern). Specifically, use a linear decay: first in-progress status gets weight N, second gets N-1, etc., normalized to sum to 1.0
     - For each in-progress status, compute:
       - `full_time_p50` = `ct_median × status_weight`
       - `full_time_p25` = `ct_q1 × status_weight`
       - `full_time_p99` = derived from the distribution shape (using same sigma as overall cycle time, scaled to per-status median)
       - `min_hours` = `full_time_p50 × (1 - spread_factor)`
       - `max_hours` = `full_time_p50 × (1 + spread_factor)`
  3. For `"todo"` statuses: set minimal wait time (p25=1, p50=2, p99=8 hours), zero work time
  4. For `"done"` statuses: set zero for everything

### R4: Plotly Visualizations on Template Page
- **Box plot chart**: Shows cycle time distribution per issue type per size from the template inputs
- **Stacked horizontal bar chart**: Shows average expected time in status for each status, for each type+size combination after distribution
  - View modes (switchable):
    - All sizes for a specific type
    - All types for a specific size
    - Single chart for a specific type showing each size
    - Overall aggregate

### R5: Apply Template to Teams
- UI: When viewing a template, show all teams with checkboxes
- "Apply" button overwrites all `TouchTimeConfig` rows for selected teams
- Available in both:
  - Team creation flow (optional template selection)
  - Existing team workflow editor (button to apply template)
- Application is destructive (replaces existing timing configs)

---

## Data Model

### New DB Tables

```
timing_templates
├── id (PK)
├── name (unique, str)
├── description (str, nullable)
├── spread_factor (float, default 0.33)
├── created_at, updated_at

timing_template_entries
├── id (PK)
├── template_id (FK → timing_templates)
├── issue_type (str)
├── story_points (int)
├── ct_min (float, hours)
├── ct_q1 (float, hours)
├── ct_median (float, hours)
├── ct_q3 (float, hours)
├── ct_max (float, hours)
├── UNIQUE(template_id, issue_type, story_points)
```

### Modified Tables

```
workflow_steps
├── + status_category (str, nullable, values: "todo" | "in_progress" | "done")
```

---

## API Endpoints

```
# Templates CRUD
GET    /templates                              → list all templates
POST   /templates                              → create template
GET    /templates/{id}                          → get template with entries
PUT    /templates/{id}                          → update template (name, description, spread_factor, entries)
DELETE /templates/{id}                          → delete template

# Template preview (compute distribution without applying)
POST   /templates/{id}/preview?team_id={tid}   → returns computed TouchTimeConfigs for preview

# Apply template to teams
POST   /templates/{id}/apply                   → body: { team_ids: [1, 2, 3] }
```

---

## Implementation Plan

### Phase 1: Backend — Status Category
1. Add `status_category` column to `WorkflowStep` model
2. Alembic migration
3. Update `WorkflowStepInput`/`WorkflowStepRead`/`WorkflowStepUpdate` schemas
4. Update workflow API to accept/return `status_category`

### Phase 2: Backend — Template Model & CRUD
5. Create `TimingTemplate` and `TimingTemplateEntry` models
6. Alembic migration
7. Create Pydantic schemas for template CRUD
8. Create `/templates` API router with CRUD endpoints
9. Register router in `main.py`

### Phase 3: Backend — Distribution Engine & Apply
10. Create `template_engine.py` with:
    - `compute_p99_from_boxplot(ct_min, ct_q1, ct_median, ct_q3, ct_max)`
    - `distribute_cycle_time(entry, in_progress_steps, spread_factor)`
    - `apply_template_to_team(template, team, db)`
11. Add `/templates/{id}/preview` endpoint
12. Add `/templates/{id}/apply` endpoint

### Phase 4: Frontend — Status Category UI
13. Update `WorkflowStep` type to include `status_category`
14. Add status category selector in `WorkflowDesigner` step rows

### Phase 5: Frontend — Template Management Page
15. Install `react-plotly.js` and `plotly.js`
16. Add "Templates" section to navigation
17. Create `TemplateList` component (list + create/delete)
18. Create `TemplateEditor` component:
    - Name, description, spread factor inputs
    - Grid for entering cycle time box plot per type+size
    - Plotly box plot visualization
19. Create `TemplatePreviewChart` component:
    - Stacked horizontal bar chart showing per-status distribution
    - View mode switcher (by type, by size, single type+sizes, overall)

### Phase 6: Frontend — Apply Template Flow
20. Create `ApplyTemplateModal` — team selector with checkboxes + apply button
21. Add "Apply Template" button in `WorkflowDesigner`
22. Add optional template selector in `AddTeamModal`
23. Create API hooks: `useTemplates()`, `useTemplate(id)`, `useCreateTemplate()`, `useUpdateTemplate()`, `useDeleteTemplate()`, `useApplyTemplate()`, `usePreviewTemplate()`

---

## Distribution Math Details

### P99 Derivation from Box Plot
Given box plot inputs (min, q1, median, q3, max):
- `p25 = q1` (by definition)
- `p50 = median` (by definition)
- `IQR = q3 - q1`
- For log-normal: `sigma = ln(q3/q1) / (2 × 0.6745)`
- `p99 = median × exp(2.3263 × sigma)`

### Per-Status Weight (Linear Decay)
For N in-progress statuses:
- Status at position i (0-indexed) gets weight `(N - i)`
- Normalize: `weight_i = (N - i) / sum(1..N)`
- Example: 3 statuses → weights [3/6, 2/6, 1/6] = [0.50, 0.33, 0.17]

### Work Duration from Median
- `min_hours = p50_per_status × (1 - spread_factor)`
- `max_hours = p50_per_status × (1 + spread_factor)`
- Default spread_factor = 0.33 → range is [0.67 × median, 1.33 × median]
