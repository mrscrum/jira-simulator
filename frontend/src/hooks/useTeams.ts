import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { TeamCreate, TeamUpdate } from "@/lib/types";

export function useTeams() {
  return useQuery({
    queryKey: ["teams"],
    queryFn: api.fetchTeams,
  });
}

export function useTeam(teamId: number) {
  return useQuery({
    queryKey: ["teams", teamId],
    queryFn: () => api.fetchTeam(teamId),
    enabled: teamId > 0,
  });
}

export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TeamCreate) => api.createTeam(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useUpdateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TeamUpdate }) =>
      api.updateTeam(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useDeleteTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteTeam(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["teams"] }),
  });
}
