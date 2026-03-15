import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { WorkflowStepInput } from "@/lib/types";

export function useWorkflow(teamId: number | null) {
  return useQuery({
    queryKey: ["workflow", teamId],
    queryFn: () => api.fetchWorkflow(teamId!),
    enabled: teamId !== null,
  });
}

export function useReplaceWorkflow(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (steps: WorkflowStepInput[]) =>
      api.replaceWorkflow(teamId, steps),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["workflow", teamId] }),
  });
}

export function useAddWorkflowStep(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkflowStepInput) =>
      api.addWorkflowStep(teamId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["workflow", teamId] }),
  });
}

export function useDeleteWorkflowStep(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (stepId: number) => api.deleteWorkflowStep(teamId, stepId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["workflow", teamId] }),
  });
}
