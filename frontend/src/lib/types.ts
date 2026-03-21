export interface Team {
  id: number;
  name: string;
  jira_project_key: string;
  jira_board_id: number | null;
  organization_id: number;
  is_active: boolean;
  sprint_length_days: number;
  working_hours_start: number;
  working_hours_end: number;
  timezone: string;
  sprint_capacity_min: number;
  sprint_capacity_max: number;
  priority_randomization: boolean;
  tick_duration_hours: number;
  created_at: string;
  updated_at: string;
}

export interface TeamCreate {
  name: string;
  jira_project_key: string;
  jira_board_id?: number | null;
  sprint_length_days?: number;
  sprint_capacity_min?: number;
  sprint_capacity_max?: number;
  priority_randomization?: boolean;
  tick_duration_hours?: number;
  working_hours_start?: number;
  working_hours_end?: number;
  timezone?: string;
}

export interface TeamUpdate {
  name?: string;
  jira_project_key?: string;
  jira_board_id?: number | null;
  sprint_length_days?: number;
  sprint_capacity_min?: number;
  sprint_capacity_max?: number;
  priority_randomization?: boolean;
  tick_duration_hours?: number;
  working_hours_start?: number;
  working_hours_end?: number;
  timezone?: string;
}

export interface Member {
  id: number;
  team_id: number;
  name: string;
  role: string;
  daily_capacity_hours: number;
  max_concurrent_wip: number;
  created_at: string;
  updated_at: string;
}

export interface MemberCreate {
  name: string;
  role: string;
  daily_capacity_hours?: number;
  max_concurrent_wip?: number;
}

export interface MemberUpdate {
  name?: string;
  role?: string;
  daily_capacity_hours?: number;
  max_concurrent_wip?: number;
}

export interface TouchTimeConfig {
  id: number;
  workflow_step_id: number;
  issue_type: string;
  story_points: number;
  min_hours: number;
  max_hours: number;
  full_time_p25: number | null;
  full_time_p50: number | null;
  full_time_p99: number | null;
  created_at: string;
  updated_at: string;
}

export interface TouchTimeConfigInput {
  issue_type: string;
  story_points: number;
  min_hours: number;
  max_hours: number;
  full_time_p25?: number | null;
  full_time_p50?: number | null;
  full_time_p99?: number | null;
}

export interface WorkflowStep {
  id: number;
  workflow_id: number;
  jira_status: string;
  role_required: string;
  roles_json: string | null;
  order: number;
  max_wait_hours: number;
  wip_contribution: number;
  status_category: string | null;
  touch_time_configs: TouchTimeConfig[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowStepInput {
  jira_status: string;
  role_required: string;
  roles_json?: string | null;
  order: number;
  max_wait_hours?: number;
  wip_contribution?: number;
  status_category?: string | null;
  touch_time_configs?: TouchTimeConfigInput[];
}

export interface WorkflowStepUpdate {
  jira_status?: string;
  role_required?: string;
  roles_json?: string | null;
  order?: number;
  max_wait_hours?: number;
  wip_contribution?: number;
  status_category?: string | null;
}

export interface Workflow {
  id: number;
  team_id: number;
  name: string;
  description: string | null;
  steps: WorkflowStep[];
  created_at: string;
  updated_at: string;
}

export interface CrossTeamDependency {
  id: number;
  source_team_id: number;
  target_team_id: number;
  dependency_type: string;
  created_at: string;
  updated_at: string;
}

export interface CrossTeamDependencyCreate {
  source_team_id: number;
  target_team_id: number;
  dependency_type: string;
}

// Move-left configuration
export interface MoveLeftTarget {
  id: number;
  move_left_config_id: number;
  to_step_id: number;
  weight: number;
}

export interface MoveLeftConfig {
  id: number;
  team_id: number;
  from_step_id: number;
  base_probability: number;
  issue_type: string | null;
  story_points: number | null;
  targets: MoveLeftTarget[];
}

export interface MoveLeftTargetInput {
  to_step_id: number;
  weight: number;
}

export interface MoveLeftConfigInput {
  from_step_id: number;
  base_probability: number;
  issue_type?: string | null;
  story_points?: number | null;
  targets: MoveLeftTargetInput[];
}

// Simulation
export interface SimulationStatus {
  status: string;
  tick_count: number;
  clock_speed: number;
  sim_time: string;
  last_successful_tick: string | null;
  teams: TeamSprintStatus[];
}

export interface TeamSprintStatus {
  team_id: number;
  team_name: string;
  sprint_number: number;
  sprint_name: string | null;
  phase: string | null;
  status: string | null;
  committed_points: number;
  completed_points: number;
  total_sprints: number;
}

export interface TickInterval {
  minutes: number;
}

export interface JiraStatus {
  name: string;
  category: string;
}

// Timing Templates
export interface TimingTemplateEntry {
  id: number;
  template_id: number;
  issue_type: string;
  story_points: number;
  ct_min: number;
  ct_q1: number;
  ct_median: number;
  ct_q3: number;
  ct_max: number;
  created_at: string;
  updated_at: string;
}

export interface TimingTemplateEntryInput {
  issue_type: string;
  story_points: number;
  ct_min: number;
  ct_q1: number;
  ct_median: number;
  ct_q3: number;
  ct_max: number;
}

export interface TimingTemplate {
  id: number;
  name: string;
  description: string | null;
  spread_factor: number;
  entries: TimingTemplateEntry[];
  created_at: string;
  updated_at: string;
}

export interface TimingTemplateCreate {
  name: string;
  description?: string | null;
  spread_factor?: number;
  entries: TimingTemplateEntryInput[];
}

export interface TimingTemplateUpdate {
  name?: string;
  description?: string | null;
  spread_factor?: number;
  entries?: TimingTemplateEntryInput[];
}

export interface PreviewConfigItem {
  workflow_step_id: number;
  jira_status: string;
  status_category: string | null;
  issue_type: string;
  story_points: number;
  min_hours: number;
  max_hours: number;
  full_time_p25: number | null;
  full_time_p50: number | null;
  full_time_p99: number | null;
}

export interface TemplatePreviewResponse {
  template_id: number;
  team_id: number;
  configs: PreviewConfigItem[];
}

export interface TemplateApplyRequest {
  team_ids: number[];
}
