import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useTeams } from "@/hooks/useTeams";
import { useApplyTemplate, usePreviewTemplate } from "@/hooks/useTemplates";
import { StatusDistributionChart } from "./StatusDistributionChart";

interface ApplyTemplatePanelProps {
  templateId: number;
}

export function ApplyTemplatePanel({ templateId }: ApplyTemplatePanelProps) {
  const { data: teams = [] } = useTeams();
  const applyTemplate = useApplyTemplate();
  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>([]);
  const [previewTeamId, setPreviewTeamId] = useState<number | null>(null);
  const { data: preview } = usePreviewTemplate(templateId, previewTeamId);
  const [applied, setApplied] = useState(false);

  // Auto-select the first team for preview so the chart shows immediately
  useEffect(() => {
    if (previewTeamId === null && teams.length > 0) {
      setPreviewTeamId(teams[0].id);
    }
  }, [teams, previewTeamId]);

  const toggleTeam = (teamId: number) => {
    setSelectedTeamIds((prev) =>
      prev.includes(teamId) ? prev.filter((id) => id !== teamId) : [...prev, teamId],
    );
  };

  const handleApply = () => {
    if (selectedTeamIds.length === 0) return;
    applyTemplate.mutate(
      { templateId, data: { team_ids: selectedTeamIds } },
      {
        onSuccess: () => {
          setApplied(true);
          setTimeout(() => setApplied(false), 3000);
        },
      },
    );
  };

  const previewTeamName = teams.find((t) => t.id === previewTeamId)?.name;

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">Apply Template to Teams</h3>

      <div className="rounded-lg border p-3">
        <div className="space-y-1">
          {teams.map((team) => (
            <label
              key={team.id}
              className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-accent/50 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selectedTeamIds.includes(team.id)}
                onChange={() => toggleTeam(team.id)}
                className="rounded"
              />
              <span>{team.name}</span>
              <Button
                variant={previewTeamId === team.id ? "default" : "ghost"}
                size="sm"
                className="ml-auto h-5 px-2 text-[10px]"
                onClick={(e) => {
                  e.preventDefault();
                  setPreviewTeamId(team.id);
                }}
              >
                {previewTeamId === team.id ? "Previewing" : "Preview"}
              </Button>
            </label>
          ))}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <Button
            size="sm"
            disabled={selectedTeamIds.length === 0 || applyTemplate.isPending}
            onClick={handleApply}
          >
            {applyTemplate.isPending
              ? "Applying..."
              : `Apply to ${selectedTeamIds.length} team${selectedTeamIds.length !== 1 ? "s" : ""}`}
          </Button>
          {applied && (
            <span className="text-xs text-green-600">Template applied successfully!</span>
          )}
        </div>
      </div>

      {/* Status distribution chart — always visible when preview data exists */}
      {preview && preview.configs.length > 0 && (
        <div>
          <p className="mb-2 text-xs text-muted-foreground">
            Expected time in status for <strong>{previewTeamName}</strong> workflow:
          </p>
          <StatusDistributionChart configs={preview.configs} />
        </div>
      )}

      {preview && preview.configs.length === 0 && previewTeamId && (
        <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
          No preview available. Make sure the team&apos;s workflow has steps with status categories set
          (or at least 2+ steps for auto-inference).
        </div>
      )}
    </div>
  );
}
