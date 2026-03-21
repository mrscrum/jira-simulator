import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useTeams } from "@/hooks/useTeams";
import { useApplyTemplate } from "@/hooks/useTemplates";

interface ApplyTemplatePanelProps {
  templateId: number;
}

export function ApplyTemplatePanel({ templateId }: ApplyTemplatePanelProps) {
  const { data: teams = [] } = useTeams();
  const applyTemplate = useApplyTemplate();
  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>([]);
  const [applied, setApplied] = useState(false);

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

      <p className="text-xs text-muted-foreground">
        After applying, view the &quot;Expected Time in Status&quot; chart in each team&apos;s Workflow section.
      </p>
    </div>
  );
}
