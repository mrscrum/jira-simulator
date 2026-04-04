import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelAllPendingEvents,
  cancelScheduledEvent,
  fetchAuditSummary,
  fetchFlowMatrix,
  fetchItemEvents,
  fetchScheduledEvents,
  fetchSprintItems,
  fetchTeamSprints,
  modifyScheduledEvent,
  recomputeSprint,
  triggerManualDispatch,
  triggerPrecomputation,
} from "@/lib/api";

export function useTeamSprints(teamId: number | null) {
  return useQuery({
    queryKey: ["team-sprints", teamId],
    queryFn: () => fetchTeamSprints(teamId!),
    enabled: !!teamId,
    refetchInterval: 30_000,
  });
}

export function useScheduledEvents(
  teamId: number | null,
  sprintId: number | null,
  params?: { status?: string; event_type?: string; page?: number; page_size?: number },
) {
  return useQuery({
    queryKey: ["scheduled-events", teamId, sprintId, params],
    queryFn: () => fetchScheduledEvents(teamId!, sprintId!, params),
    enabled: !!teamId && !!sprintId,
    refetchInterval: 10_000,
  });
}

export function useAuditSummary(
  teamId: number | null,
  sprintId: number | null,
) {
  return useQuery({
    queryKey: ["audit-summary", teamId, sprintId],
    queryFn: () => fetchAuditSummary(teamId!, sprintId!),
    enabled: !!teamId && !!sprintId,
    refetchInterval: 30_000,
  });
}

export function useCancelEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, reason }: { eventId: number; reason?: string }) =>
      cancelScheduledEvent(eventId, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scheduled-events"] });
      qc.invalidateQueries({ queryKey: ["audit-summary"] });
    },
  });
}

export function useModifyEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      eventId,
      data,
    }: {
      eventId: number;
      data: { scheduled_at?: string; payload?: Record<string, unknown> };
    }) => modifyScheduledEvent(eventId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scheduled-events"] });
    },
  });
}

export function useCancelAllEvents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      teamId,
      sprintId,
    }: {
      teamId: number;
      sprintId: number;
    }) => cancelAllPendingEvents(teamId, sprintId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scheduled-events"] });
      qc.invalidateQueries({ queryKey: ["audit-summary"] });
    },
  });
}

export function usePrecompute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      teamId,
      rngSeed,
    }: {
      teamId: number;
      rngSeed?: number;
    }) => triggerPrecomputation(teamId, rngSeed),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scheduled-events"] });
      qc.invalidateQueries({ queryKey: ["audit-summary"] });
      qc.invalidateQueries({ queryKey: ["team-sprints"] });
    },
  });
}

export function useRecompute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      teamId,
      sprintId,
      rngSeed,
    }: {
      teamId: number;
      sprintId: number;
      rngSeed?: number;
    }) => recomputeSprint(teamId, sprintId, rngSeed),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scheduled-events"] });
      qc.invalidateQueries({ queryKey: ["audit-summary"] });
      qc.invalidateQueries({ queryKey: ["team-sprints"] });
    },
  });
}

export function useSprintItems(teamId: number | null, sprintId: number | null) {
  return useQuery({
    queryKey: ["sprint-items", teamId, sprintId],
    queryFn: () => fetchSprintItems(teamId!, sprintId!),
    enabled: !!teamId && !!sprintId,
    refetchInterval: 30_000,
  });
}

export function useItemEvents(
  teamId: number | null,
  sprintId: number | null,
  issueId: number | null,
) {
  return useQuery({
    queryKey: ["item-events", teamId, sprintId, issueId],
    queryFn: () => fetchItemEvents(teamId!, sprintId!, issueId!),
    enabled: !!teamId && !!sprintId && !!issueId,
  });
}

export function useFlowMatrix(teamId: number | null, sprintId: number | null) {
  return useQuery({
    queryKey: ["flow-matrix", teamId, sprintId],
    queryFn: () => fetchFlowMatrix(teamId!, sprintId!),
    enabled: !!teamId && !!sprintId,
    refetchInterval: 30_000,
  });
}

export function useManualDispatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => triggerManualDispatch(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scheduled-events"] });
      qc.invalidateQueries({ queryKey: ["audit-summary"] });
    },
  });
}
