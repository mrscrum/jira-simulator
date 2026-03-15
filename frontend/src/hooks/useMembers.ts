import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { MemberCreate, MemberUpdate } from "@/lib/types";

export function useMembers(teamId: number | null) {
  return useQuery({
    queryKey: ["members", teamId],
    queryFn: () => api.fetchMembers(teamId!),
    enabled: teamId !== null,
  });
}

export function useCreateMember(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: MemberCreate) => api.createMember(teamId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["members", teamId] }),
  });
}

export function useUpdateMember(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, data }: { memberId: number; data: MemberUpdate }) =>
      api.updateMember(teamId, memberId, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["members", teamId] }),
  });
}

export function useDeleteMember(teamId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memberId: number) => api.deleteMember(teamId, memberId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["members", teamId] }),
  });
}
