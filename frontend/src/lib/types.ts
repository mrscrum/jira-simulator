export interface Team {
  id: number;
  name: string;
  jira_project_key: string;
  jira_board_id: number | null;
  organization_id: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TeamCreate {
  name: string;
  jira_project_key: string;
  jira_board_id?: number | null;
}

export interface TeamUpdate {
  name?: string;
  jira_project_key?: string;
  jira_board_id?: number | null;
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
  created_at: string;
  updated_at: string;
}

export interface TouchTimeConfigInput {
  issue_type: string;
  story_points: number;
  min_hours: number;
  max_hours: number;
}

export interface WorkflowStep {
  id: number;
  workflow_id: number;
  jira_status: string;
  role_required: string;
  order: number;
  max_wait_hours: number;
  wip_contribution: number;
  touch_time_configs: TouchTimeConfig[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowStepInput {
  jira_status: string;
  role_required: string;
  order: number;
  max_wait_hours?: number;
  wip_contribution?: number;
  touch_time_configs?: TouchTimeConfigInput[];
}

export interface WorkflowStepUpdate {
  jira_status?: string;
  role_required?: string;
  order?: number;
  max_wait_hours?: number;
  wip_contribution?: number;
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

export interface DysfunctionConfig {
  id: number;
  team_id: number;
  low_quality_probability: number;
  scope_creep_probability: number;
  blocking_dep_probability: number;
  dark_teammate_probability: number;
  re_estimation_probability: number;
  bug_injection_probability: number;
  cross_team_block_probability: number;
  cross_team_handoff_lag_probability: number;
  cross_team_bug_probability: number;
  // Low quality detail fields
  low_quality_ba_po_touch_min: number;
  low_quality_ba_po_touch_max: number;
  low_quality_qa_touch_min: number;
  low_quality_qa_touch_max: number;
  low_quality_dev_rework_min: number;
  low_quality_dev_rework_max: number;
  low_quality_cycle_back_probability: number;
  low_quality_sp_bloat_min: number;
  low_quality_sp_bloat_max: number;
  low_quality_severity_weight: number;
  // Scope creep detail fields
  scope_creep_sp_increase_min: number;
  scope_creep_sp_increase_max: number;
  scope_creep_new_subtask_probability: number;
  scope_creep_subtask_sp_min: number;
  scope_creep_subtask_sp_max: number;
  scope_creep_mid_sprint_only: number;
  // Blocking dependency detail fields
  blocking_dep_wait_hours_min: number;
  blocking_dep_escalation_wait_hours: number;
  // Dark teammate detail fields
  dark_teammate_capacity_reduction_min: number;
  dark_teammate_capacity_reduction_max: number;
  dark_teammate_absence_days_max: number;
  // Re-estimation detail fields
  re_estimation_sp_change_min: number;
  re_estimation_sp_change_max: number;
  re_estimation_trigger_threshold_pct: number;
  // Bug injection detail fields
  bug_injection_sp_weight_1: number;
  bug_injection_sp_weight_2: number;
  bug_injection_sp_weight_3: number;
  bug_injection_severity_distribution: number;
  created_at: string;
  updated_at: string;
}

export type DysfunctionConfigUpdate = Partial<
  Omit<DysfunctionConfig, "id" | "team_id" | "created_at" | "updated_at">
>;

export type DysfunctionType =
  | "low_quality"
  | "scope_creep"
  | "blocking_dependency"
  | "dark_teammate"
  | "re_estimation"
  | "bug_injection"
  | "cross_team_block"
  | "cross_team_handoff_lag"
  | "cross_team_bug";

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

export interface SimulationStatus {
  status: string;
  tick_count?: number;
  last_successful_tick?: string | null;
}

export interface TickInterval {
  minutes: number;
}

export interface InjectRequest {
  team_id: number;
  dysfunction_type: string;
  target_issue_id?: number;
  target_member_id?: number;
}

export interface JiraStatus {
  name: string;
  category: string;
}
