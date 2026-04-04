import type {
  CrossTeamDependency,
  CrossTeamDependencyCreate,
  JiraStatus,
  Member,
  MemberCreate,
  MemberUpdate,
  MoveLeftConfig,
  MoveLeftConfigInput,
  SimulationStatus,
  Team,
  TeamCreate,
  TeamUpdate,
  TickInterval,
  Workflow,
  WorkflowStep,
  WorkflowStepInput,
  WorkflowStepUpdate,
  TimingTemplate,
  TimingTemplateCreate,
  TimingTemplateUpdate,
  TemplateApplyRequest,
  TemplatePreviewResponse,
} from "./types";

const BASE_URL = "/api";

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Teams
export const fetchTeams = () => request<Team[]>("/teams");
export const fetchTeam = (id: number) => request<Team>(`/teams/${id}`);
export const createTeam = (data: TeamCreate) =>
  request<Team>("/teams", { method: "POST", body: JSON.stringify(data) });
export const updateTeam = (id: number, data: TeamUpdate) =>
  request<Team>(`/teams/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteTeam = (id: number) =>
  request<Team>(`/teams/${id}`, { method: "DELETE" });

// Members
export const fetchMembers = (teamId: number) =>
  request<Member[]>(`/teams/${teamId}/members`);
export const createMember = (teamId: number, data: MemberCreate) =>
  request<Member>(`/teams/${teamId}/members`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const updateMember = (
  teamId: number,
  memberId: number,
  data: MemberUpdate,
) =>
  request<Member>(`/teams/${teamId}/members/${memberId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
export const deleteMember = (teamId: number, memberId: number) =>
  request<Member>(`/teams/${teamId}/members/${memberId}`, {
    method: "DELETE",
  });

// Workflow
export const fetchWorkflow = (teamId: number) =>
  request<Workflow>(`/teams/${teamId}/workflow`);
export const replaceWorkflow = (
  teamId: number,
  steps: WorkflowStepInput[],
) =>
  request<Workflow>(`/teams/${teamId}/workflow`, {
    method: "PUT",
    body: JSON.stringify({ steps }),
  });
export const addWorkflowStep = (
  teamId: number,
  data: WorkflowStepInput,
) =>
  request<WorkflowStep>(`/teams/${teamId}/workflow/steps`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const updateWorkflowStep = (
  teamId: number,
  stepId: number,
  data: WorkflowStepUpdate,
) =>
  request<WorkflowStep>(`/teams/${teamId}/workflow/steps/${stepId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
export const deleteWorkflowStep = (teamId: number, stepId: number) =>
  request<WorkflowStep>(`/teams/${teamId}/workflow/steps/${stepId}`, {
    method: "DELETE",
  });

// Move-left configs
export const fetchMoveLeftConfigs = (teamId: number) =>
  request<MoveLeftConfig[]>(`/teams/${teamId}/move-left`);
export const replaceMoveLeftConfigs = (
  teamId: number,
  configs: MoveLeftConfigInput[],
) =>
  request<MoveLeftConfig[]>(`/teams/${teamId}/move-left`, {
    method: "PUT",
    body: JSON.stringify({ configs }),
  });

// Dependencies
export const fetchDependencies = () =>
  request<CrossTeamDependency[]>("/dependencies");
export const createDependency = (data: CrossTeamDependencyCreate) =>
  request<CrossTeamDependency>("/dependencies", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const deleteDependency = (id: number) =>
  request<CrossTeamDependency>(`/dependencies/${id}`, {
    method: "DELETE",
  });

// Simulation
export const fetchSimulationStatus = () =>
  request<SimulationStatus>("/simulation/status");
export const startSimulation = () =>
  request<SimulationStatus>("/simulation/start", { method: "POST" });
export const pauseSimulation = () =>
  request<SimulationStatus>("/simulation/pause", { method: "POST" });
export const resetSimulation = () =>
  request<SimulationStatus>("/simulation/reset", { method: "POST" });
export const updateTickInterval = (minutes: number) =>
  request<TickInterval>("/simulation/tick-interval", {
    method: "PUT",
    body: JSON.stringify({ minutes }),
  });
export const triggerManualTick = () =>
  request<Record<string, unknown>>("/simulation/tick", { method: "POST" });

// Clock speed
export const fetchClockSpeed = () =>
  request<{ speed: number }>("/simulation/clock");
export const setClockSpeed = (speed: number) =>
  request<{ speed: number }>("/simulation/clock", {
    method: "PUT",
    body: JSON.stringify({ speed }),
  });

// E2E setup
export const setupE2E = () =>
  request<{ teams: Array<Record<string, unknown>> }>("/e2e/setup", {
    method: "POST",
  });

// Templates
export const fetchTemplates = () =>
  request<TimingTemplate[]>("/templates");
export const fetchTemplate = (id: number) =>
  request<TimingTemplate>(`/templates/${id}`);
export const createTemplate = (data: TimingTemplateCreate) =>
  request<TimingTemplate>("/templates", { method: "POST", body: JSON.stringify(data) });
export const updateTemplate = (id: number, data: TimingTemplateUpdate) =>
  request<TimingTemplate>(`/templates/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteTemplate = (id: number) =>
  request<void>(`/templates/${id}`, { method: "DELETE" });
export const previewTemplate = (templateId: number, teamId: number) =>
  request<TemplatePreviewResponse>(`/templates/${templateId}/preview?team_id=${teamId}`, { method: "POST" });
export const applyTemplate = (templateId: number, data: TemplateApplyRequest) =>
  request<{ applied_to: number }>(`/templates/${templateId}/apply`, { method: "POST", body: JSON.stringify(data) });

// Jira Proxy
export const fetchJiraStatuses = (projectKey: string) =>
  request<JiraStatus[]>(`/jira/projects/${projectKey}/statuses`);

// Sprints
import type {
  SprintSummary,
} from "./types";

export const fetchTeamSprints = (teamId: number) =>
  request<SprintSummary[]>(`/teams/${teamId}/sprints`);

// Scheduled Events
import type {
  ScheduledEvent,
  ScheduledEventListResponse,
  AuditSummary,
  PrecomputeResponse,
} from "./types";

export const fetchScheduledEvents = (
  teamId: number,
  sprintId: number,
  params?: { status?: string; event_type?: string; page?: number; page_size?: number },
) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request<ScheduledEventListResponse>(
    `/teams/${teamId}/sprints/${sprintId}/events${q ? `?${q}` : ""}`,
  );
};

export const fetchScheduledEvent = (eventId: number) =>
  request<ScheduledEvent>(`/scheduled-events/${eventId}`);

export const cancelScheduledEvent = (eventId: number, reason?: string) =>
  request<{ deleted: boolean; id: number }>(`/scheduled-events/${eventId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null }),
  });

export const modifyScheduledEvent = (
  eventId: number,
  data: { scheduled_at?: string; payload?: Record<string, unknown> },
) =>
  request<ScheduledEvent>(`/scheduled-events/${eventId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const cancelAllPendingEvents = (teamId: number, sprintId: number) =>
  request<{ deleted: number }>(
    `/teams/${teamId}/sprints/${sprintId}/events/cancel-all`,
    { method: "POST" },
  );

export const triggerPrecomputation = (teamId: number, rngSeed?: number) =>
  request<PrecomputeResponse>(`/teams/${teamId}/sprints/precompute`, {
    method: "POST",
    body: JSON.stringify({ rng_seed: rngSeed ?? null }),
  });

export const recomputeSprint = (
  teamId: number,
  sprintId: number,
  rngSeed?: number,
) =>
  request<PrecomputeResponse>(
    `/teams/${teamId}/sprints/${sprintId}/recompute`,
    { method: "POST", body: JSON.stringify({ rng_seed: rngSeed ?? null }) },
  );

export const triggerManualDispatch = () =>
  request<{ dispatched: number }>("/simulation/dispatch", { method: "POST" });

export const fetchAuditSummary = (teamId: number, sprintId: number) =>
  request<AuditSummary>(`/teams/${teamId}/sprints/${sprintId}/audit`);

// Sprint Items
import type { SprintItem, FlowMatrixData } from "./types";

export const fetchSprintItems = (teamId: number, sprintId: number) =>
  request<SprintItem[]>(`/teams/${teamId}/sprints/${sprintId}/items`);

export const fetchItemEvents = (teamId: number, sprintId: number, issueId: number) =>
  request<ScheduledEvent[]>(
    `/teams/${teamId}/sprints/${sprintId}/items/${issueId}/events`,
  );

export const fetchFlowMatrix = (teamId: number, sprintId: number) =>
  request<FlowMatrixData>(`/teams/${teamId}/sprints/${sprintId}/flow-matrix`);
