import type {
  CrossTeamDependency,
  CrossTeamDependencyCreate,
  DysfunctionConfig,
  DysfunctionConfigUpdate,
  DysfunctionType,
  InjectRequest,
  JiraStatus,
  Member,
  MemberCreate,
  MemberUpdate,
  SimulationStatus,
  Team,
  TeamCreate,
  TeamUpdate,
  TickInterval,
  Workflow,
  WorkflowStep,
  WorkflowStepInput,
  WorkflowStepUpdate,
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

// Dysfunctions
export const fetchDysfunctions = (teamId: number) =>
  request<DysfunctionConfig>(`/teams/${teamId}/dysfunctions`);
export const updateDysfunction = (
  teamId: number,
  type: DysfunctionType,
  data: DysfunctionConfigUpdate,
) =>
  request<DysfunctionConfig>(`/teams/${teamId}/dysfunctions/${type}`, {
    method: "PUT",
    body: JSON.stringify(data),
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
export const injectDysfunction = (data: InjectRequest) =>
  request<{ injected: boolean }>("/simulate/inject", {
    method: "POST",
    body: JSON.stringify(data),
  });

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

// Jira Proxy
export const fetchJiraStatuses = (projectKey: string) =>
  request<JiraStatus[]>(`/jira/projects/${projectKey}/statuses`);
