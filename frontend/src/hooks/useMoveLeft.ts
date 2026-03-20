import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { MoveLeftConfigInput } from "@/lib/types";

export function useMoveLeftConfigs(teamId: number) {
  return useQuery({
    queryKey: ["move-left", teamId],
    queryFn: () => api.fetchMoveLeftConfigs(teamId),
    enabled: teamId > 0,
  });
}

export function useReplaceMoveLeftConfigs(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (configs: MoveLeftConfigInput[]) =>
      api.replaceMoveLeftConfigs(teamId, configs),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["move-left", teamId] }),
  });
}
