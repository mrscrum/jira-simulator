import { useQuery } from "@tanstack/react-query";
import * as api from "@/lib/api";

export function useJiraStatuses(projectKey: string | null) {
  return useQuery({
    queryKey: ["jira-statuses", projectKey],
    queryFn: () => api.fetchJiraStatuses(projectKey!),
    enabled: projectKey !== null && projectKey.length > 0,
  });
}
