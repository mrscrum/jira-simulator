import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import type { TimingTemplateCreate, TimingTemplateUpdate, TemplateApplyRequest } from "@/lib/types";

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: api.fetchTemplates,
  });
}

export function useTemplate(id: number | null) {
  return useQuery({
    queryKey: ["templates", id],
    queryFn: () => api.fetchTemplate(id!),
    enabled: id !== null,
  });
}

export function useCreateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TimingTemplateCreate) => api.createTemplate(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function useUpdateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TimingTemplateUpdate }) =>
      api.updateTemplate(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteTemplate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["templates"] }),
  });
}

export function usePreviewTemplate(templateId: number | null, teamId: number | null) {
  return useQuery({
    queryKey: ["template-preview", templateId, teamId],
    queryFn: () => api.previewTemplate(templateId!, teamId!),
    enabled: templateId !== null && teamId !== null,
  });
}

export function useApplyTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, data }: { templateId: number; data: TemplateApplyRequest }) =>
      api.applyTemplate(templateId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflow"] });
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
  });
}
