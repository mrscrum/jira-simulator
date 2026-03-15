import type { DysfunctionType } from "./types";

export interface DysfunctionMeta {
  type: DysfunctionType;
  name: string;
  description: string;
  probabilityField: string;
  modalFields: { key: string; label: string }[];
}

export const DYSFUNCTIONS: DysfunctionMeta[] = [
  {
    type: "low_quality",
    name: "Low Quality Story",
    description: "Stories produced with insufficient quality, requiring rework",
    probabilityField: "low_quality_probability",
    modalFields: [
      { key: "low_quality_ba_po_touch_min", label: "BA/PO touch min x" },
      { key: "low_quality_ba_po_touch_max", label: "BA/PO touch max x" },
      { key: "low_quality_qa_touch_min", label: "QA touch min x" },
      { key: "low_quality_qa_touch_max", label: "QA touch max x" },
      { key: "low_quality_dev_rework_min", label: "Dev rework min x" },
      { key: "low_quality_dev_rework_max", label: "Dev rework max x" },
      { key: "low_quality_cycle_back_probability", label: "Cycle-back %" },
      { key: "low_quality_sp_bloat_min", label: "SP bloat min" },
      { key: "low_quality_sp_bloat_max", label: "SP bloat max" },
      { key: "low_quality_severity_weight", label: "Severity weight" },
    ],
  },
  {
    type: "scope_creep",
    name: "Mid-Sprint Scope Add",
    description: "New work added mid-sprint, consuming capacity",
    probabilityField: "scope_creep_probability",
    modalFields: [
      { key: "scope_creep_sp_increase_min", label: "SP increase min" },
      { key: "scope_creep_sp_increase_max", label: "SP increase max" },
      { key: "scope_creep_new_subtask_probability", label: "New subtask %" },
      { key: "scope_creep_subtask_sp_min", label: "Subtask SP min" },
      { key: "scope_creep_subtask_sp_max", label: "Subtask SP max" },
      { key: "scope_creep_mid_sprint_only", label: "Mid-sprint only flag" },
    ],
  },
  {
    type: "blocking_dependency",
    name: "Blocking Dependency",
    description: "External dependency blocks progress on an issue",
    probabilityField: "blocking_dep_probability",
    modalFields: [
      { key: "blocking_dep_wait_hours_min", label: "Wait hours min" },
      { key: "blocking_dep_escalation_wait_hours", label: "Escalation wait (hours)" },
    ],
  },
  {
    type: "dark_teammate",
    name: "Teammate Goes Dark",
    description: "A team member becomes unavailable, reducing capacity",
    probabilityField: "dark_teammate_probability",
    modalFields: [
      { key: "dark_teammate_capacity_reduction_min", label: "Capacity reduction min" },
      { key: "dark_teammate_capacity_reduction_max", label: "Capacity reduction max" },
      { key: "dark_teammate_absence_days_max", label: "Max absence days" },
    ],
  },
  {
    type: "re_estimation",
    name: "Re-estimation",
    description: "Story points change after work begins",
    probabilityField: "re_estimation_probability",
    modalFields: [
      { key: "re_estimation_sp_change_min", label: "SP change min" },
      { key: "re_estimation_sp_change_max", label: "SP change max" },
      { key: "re_estimation_trigger_threshold_pct", label: "Trigger threshold %" },
    ],
  },
  {
    type: "bug_injection",
    name: "Bug Injection",
    description: "Development produces bugs that require fixing",
    probabilityField: "bug_injection_probability",
    modalFields: [
      { key: "bug_injection_sp_weight_1", label: "Bug SP weight (1pt)" },
      { key: "bug_injection_sp_weight_2", label: "Bug SP weight (2pt)" },
      { key: "bug_injection_sp_weight_3", label: "Bug SP weight (3pt)" },
      { key: "bug_injection_severity_distribution", label: "Severity distribution" },
    ],
  },
];
