# Stage 2 — Configuration UI Spec

## Overview

A React + Tailwind CSS single-page application served by Nginx from the EC2 instance. All configuration is persisted via the Stage 1 FastAPI backend. No simulation logic lives in the frontend — it is purely config and control.

---

## Architecture

```
frontend/
├── src/
│   ├── App.tsx                          # Router root
│   ├── lib/
│   │   ├── api.ts                       # Typed API client (fetch wrapper)
│   │   └── types.ts                     # Shared TypeScript types mirroring backend schemas
│   ├── hooks/
│   │   ├── useTeams.ts
│   │   ├── useWorkflow.ts
│   │   ├── useMembers.ts
│   │   ├── useDysfunctions.ts
│   │   ├── useDependencies.ts
│   │   └── useJiraStatuses.ts           # Fetches statuses for a given project key
│   └── components/
│       ├── layout/
│       │   ├── Shell.tsx                # Sidebar + main area wrapper
│       │   ├── Sidebar.tsx              # Team list + nav items
│       │   └── Topbar.tsx              # Title + contextual action buttons
│       ├── workflow/
│       │   ├── WorkflowDesigner.tsx     # Step list with DnD reorder
│       │   ├── StepRow.tsx              # Single draggable step card
│       │   ├── MemberPool.tsx           # Draggable member chips above steps
│       │   ├── MemberSlot.tsx           # Drop target within a step
│       │   ├── TouchTimeGrid.tsx        # Inline issue type × story points grid
│       │   └── AddStepModal.tsx         # New step form with Jira status picker
│       ├── members/
│       │   ├── MemberTable.tsx
│       │   └── AddMemberModal.tsx
│       ├── dysfunctions/
│       │   ├── DysfunctionList.tsx
│       │   ├── DysfunctionCard.tsx      # Toggle + slider + Edit button
│       │   └── DysfunctionModal.tsx     # Advanced settings + stubbed compound section
│       ├── dependencies/
│       │   └── DependencyConfig.tsx     # Dropdown rows + add/remove
│       ├── simulation/
│       │   ├── SimulationDashboard.tsx  # Stat cards + controls
│       │   └── InjectModal.tsx          # Force-trigger dysfunction form
│       └── shared/
│           ├── Modal.tsx                # Base modal wrapper
│           ├── StatusPicker.tsx         # Reusable Jira status dropdown
│           └── BrokenStepBadge.tsx      # Visual indicator for invalid status
```

---

## Section Specs

### Layout — Shell, Sidebar, Topbar

**Sidebar:**
- Left column, fixed width 220px
- Top section: team list — each team shows a colour dot + name
- Active team is highlighted
- "+ Add team" entry at the bottom of the list, dashed border
- Bottom section: nav items — Workflow, Members, Dysfunctions, Dependencies, Simulation
- Active nav item highlighted
- Teams and nav are independent — switching team re-fetches data for the active section

**Topbar:**
- Shows: `{Team name} — {Section name}`
- Subtitle line: contextual hint (e.g. "Drag to reorder steps · Drag members onto role slots")
- Right side: contextual action buttons (Save, + Add step, + Add member — depends on active section)
- Save button persists the current section's unsaved changes via API call
- Unsaved changes indicator: subtle dot on Save button when dirty state exists

**Add team modal fields:**
- Team name (text, required)
- Jira project key (text, required, uppercase enforced)
- Workflow template (select: Standard / Kanban / Custom)

---

### Workflow Designer

**Behaviour:**
- Steps rendered as a vertical list of draggable cards
- Drag handle (⠿) on the left of each card triggers reorder
- Reorder is optimistic — updates UI immediately, persists on Save
- Member pool above the step list shows all team members as draggable chips
- Each member chip shows: avatar initials, name, role label, role-coloured left border
- Each step has a member slot area — dropping a chip from the pool adds the member to that step
- Members can be removed from a slot by clicking an × on their chip
- A member can appear in multiple steps (e.g. Alice owns both Dev and Code Review)

**Step card fields (visible inline):**
- Step name
- Role badge (e.g. "Dev · max wait 4h")
- Member slots (drop targets)
- Touch time grid (see below)

**Touch time grid — inline, per step:**
- Rows: issue types (Story, Bug, Task)
- Columns: story points (1, 2, 3, 5, 8, 13)
- Each cell: two number inputs (min hours — max hours)
- Inputs are compact — 36px wide, no label, dash separator between min and max
- Validation: min must be ≤ max, both must be positive numbers

**Add step modal fields:**
- Step name (text, required)
- Jira status (StatusPicker component — see below)
- Role responsible (select: Dev / QA / BA / SM / PO)
- Max wait hours (number)
- WIP contribution (number, default 1, step 0.5)

---

### StatusPicker Component

Reusable component. Used in Add Step modal and Edit Step inline.

**Behaviour:**
- On mount: calls `GET /jira/projects/{project_key}/statuses`
- Shows a type-to-filter dropdown
- Each option displays: status name + category chip (To Do / In Progress / Done)
- Category chips are colour coded: To Do = gray, In Progress = blue, Done = green
- Loading state: spinner while fetching
- Error state: "Could not load Jira statuses — check project key and credentials" with retry button

**Validation (soft):**
- On save: if selected status is not in the fetched list, show inline warning:
  `"This status was not found in Jira. The step will be saved but may not function correctly."`
- Warning does not block save
- If a previously saved step's status disappears from Jira (detected on next load), the step card shows a `BrokenStepBadge` — amber warning icon + tooltip: "Status not found in Jira"
- Broken steps can still be edited and re-saved with a valid status

---

### Members

**Member table columns:** Avatar, Name, Role (coloured badge), Daily capacity (hours), Max concurrent WIP, Edit button

**Role colour mapping (consistent across all components):**
- Dev: blue
- QA: teal
- BA: coral
- SM: amber
- PO: purple

**Add member modal fields:**
- Name (text, required)
- Role (select)
- Daily capacity hours (number, default 7)
- Max concurrent WIP (number, default 3)

---

### Dysfunctions

**DysfunctionCard (compact row):**
- Dysfunction name + one-line description
- Probability slider (0–100%), live readout next to slider
- "Edit" button → opens DysfunctionModal
- Toggle (on/off) — disabled dysfunctions are skipped by the engine regardless of probability

**DysfunctionModal — two sections:**

Section 1 — Basic settings (always open):
- Probability (number input, mirrors the slider)
- Per-role touch time multiplier ranges (min/max pair per relevant role)
- Cycle-back probabilities where applicable
- Cascade probability boosts where applicable (e.g. bug injection probability boost)
- Escalation wait threshold in hours where applicable

Section 2 — Compound effects (stubbed, locked):
- Visually present at the bottom of the modal
- Heading: "Compound effects"
- Body: "Configure how this dysfunction interacts with others when triggered simultaneously. Available in a future update."
- Entire section has reduced opacity (0.45) and `pointer-events: none`
- No functional inputs — the visual structure matches what the final implementation will look like (placeholder fields are visible but greyed out)
- This preserves the layout contract so Stage 5 just removes the lock without redesigning

**Per-dysfunction modal fields:**

| Dysfunction | Fields |
|---|---|
| Low quality story | BA/PO touch min/max ×, Dev touch min/max ×, QA touch min/max ×, BA cycle-back %, QA cycle-back %, bug injection boost %, re-estimation boost % |
| Mid-sprint scope add | Capacity tax % (min/max), in-progress touch × (min/max), tax duration days (min/max) |
| Blocking dependency | Escalation wait threshold hours, blocker focus × |
| Teammate goes dark | Dark duration days (min/max), reassignment ramp-up % (what % of original touch time new worker gets) |
| Re-estimation | SP multiplier (min/max), descope probability % |
| Bug injection | Bug SP distribution (1/2/3 weighted), interruption tax × |

---

### Cross-team Dependencies

**Layout:** List of rows, each row is one directional dependency link

**Each row:**
- Dropdown: Team A (all teams)
- Dropdown: dependency type (blocks / shared component / cross-team handoff / cross-team bug)
- Arrow label →
- Dropdown: Team B (all teams, excludes Team A selection)
- Remove button

**Constraints:**
- Team A and Team B cannot be the same team (enforced in dropdown)
- Duplicate links (same A + type + B) are prevented on save with inline error
- "+ Add dependency" appends a new empty row

---

### Simulation Controls

**Stat cards (2×2 grid):**
- Status (Running / Paused / Stopped + sprint number)
- Tick interval
- Issues in flight
- Last tick timestamp (relative: "2 min ago")

**Controls:**
- Start / Pause / Resume button (state-dependent label)
- Reset sprint button (with confirmation dialog)
- Inject dysfunction button → opens InjectModal

**Tick interval control:**
- Slider (5–120 minutes, step 5)
- Live readout
- Takes effect on next tick (no restart needed)

**InjectModal fields:**
- Team (select, all teams)
- Dysfunction type (select, all dysfunction types)
- Target issue key (text, optional — e.g. ALPHA-42)
- Target member (select, optional — members of selected team)
- Fire button

---

## State Management

React Query for all server state:
- Each section's data is a separate query keyed by `[section, teamId]`
- On team switch: queries are refetched for the new team
- Mutations (save, add, delete) invalidate the relevant query on success
- Optimistic updates for drag-and-drop reorder (step order, member slot assignment)

Local component state only for:
- Modal open/close
- Unsaved dirty flag per section
- Drag-and-drop in-flight state

---

## API Endpoints Required from Backend (Stage 1 contract)

The frontend depends on these endpoints existing before Stage 2 can be tested end-to-end:

```
GET    /teams
POST   /teams
GET    /teams/{id}
PUT    /teams/{id}
DELETE /teams/{id}

GET    /teams/{id}/members
POST   /teams/{id}/members
PUT    /teams/{id}/members/{member_id}
DELETE /teams/{id}/members/{member_id}

GET    /teams/{id}/workflow
PUT    /teams/{id}/workflow          # Full workflow replace (steps array)
POST   /teams/{id}/workflow/steps
PUT    /teams/{id}/workflow/steps/{step_id}
DELETE /teams/{id}/workflow/steps/{step_id}

GET    /teams/{id}/dysfunctions
PUT    /teams/{id}/dysfunctions/{type}

GET    /dependencies
POST   /dependencies
DELETE /dependencies/{id}

GET    /jira/projects/{project_key}/statuses   # Proxied Jira API call

GET    /simulation/status
POST   /simulation/start
POST   /simulation/pause
POST   /simulation/reset
PUT    /simulation/tick-interval
POST   /simulate/inject
```

---

## Component Test Coverage (React Testing Library + Vitest)

Every component must have tests for:

| Component | What to test |
|---|---|
| StatusPicker | Renders options from API, filters on type, shows warning on unknown status, shows error state on API failure |
| StepRow | Renders step data, drag handle present, touch time grid inputs editable, member chip removal |
| WorkflowDesigner | Step reorder via DnD, member drop onto slot, dirty flag set on change |
| DysfunctionCard | Slider updates probability display, toggle changes enabled state, Edit opens modal |
| DysfunctionModal | All fields render, compound section visible but locked (pointer-events:none, opacity check), save calls correct API |
| DependencyConfig | Add row, remove row, duplicate detection, Team A ≠ Team B constraint |
| InjectModal | Form renders, fire calls POST /simulate/inject with correct payload |
| Shell | Team switch triggers data refetch, nav switch changes active section |

---

## UAT Criteria

Claude Code considers Stage 2 done when:

- [ ] Create a team, define a workflow from scratch with 4+ steps, assign members via drag-and-drop, configure touch time grids — save persists and survives page refresh
- [ ] Add step modal: StatusPicker loads Jira statuses, type-to-filter works, category chips display, saving an unknown status shows soft warning but saves
- [ ] BrokenStepBadge appears on a step whose Jira status was manually deleted from Jira
- [ ] Dysfunction sliders and toggles persist per team — switching teams shows different values
- [ ] Dysfunction modal: advanced fields save correctly, compound section is visible, locked, and styled at reduced opacity
- [ ] Cross-team dependency: duplicate link prevented, Team A = Team B prevented
- [ ] Simulation inject modal fires POST /simulate/inject — visible in backend logs
- [ ] All component tests green
- [ ] No TypeScript errors (`tsc --noEmit` clean)
- [ ] Ruff clean on any Python touched in this stage
