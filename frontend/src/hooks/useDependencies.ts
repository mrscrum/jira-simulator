import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { CrossTeamDependencyCreate } from "@/lib/types";

export function useDependencies() {
  return useQuery({
    queryKey: ["dependencies"],
    queryFn: api.fetchDependencies,
  });
}

export function useCreateDependency() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CrossTeamDependencyCreate) => api.createDependency(data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["dependencies"] }),
  });
}

export function useDeleteDependency() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteDependency(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["dependencies"] }),
  });
}
