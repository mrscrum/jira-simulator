import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { DysfunctionConfigUpdate, DysfunctionType } from "@/lib/types";

export function useDysfunctions(teamId: number | null) {
  return useQuery({
    queryKey: ["dysfunctions", teamId],
    queryFn: () => api.fetchDysfunctions(teamId!),
    enabled: teamId !== null,
  });
}

export function useUpdateDysfunction(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      type,
      data,
    }: {
      type: DysfunctionType;
      data: DysfunctionConfigUpdate;
    }) => api.updateDysfunction(teamId, type, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["dysfunctions", teamId] }),
  });
}
