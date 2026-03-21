import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useMoveLeftConfigs, useReplaceMoveLeftConfigs } from "@/hooks/useMoveLeft";
import type { MoveLeftConfigInput, WorkflowStep } from "@/lib/types";

const ISSUE_TYPES = ["Story", "Bug", "Task", "Spike", "Enabler"];
const STORY_POINTS = [1, 2, 3, 5, 8, 13];

interface MoveLeftGridProps {
  teamId: number;
  steps: WorkflowStep[];
}

interface LocalConfig {
  from_step_id: number;
  base_probability: string;
  to_step_id: number | null;
  issue_type: string;
  story_points: string;
}

export function MoveLeftGrid({ teamId, steps }: MoveLeftGridProps) {
  const { data: serverConfigs = [] } = useMoveLeftConfigs(teamId);
  const replaceMutation = useReplaceMoveLeftConfigs(teamId);
  const [localConfigs, setLocalConfigs] = useState<LocalConfig[]>([]);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (serverConfigs.length > 0) {
      setLocalConfigs(
        serverConfigs.map((c) => ({
          from_step_id: c.from_step_id,
          base_probability: String(c.base_probability),
          to_step_id: c.targets[0]?.to_step_id ?? null,
          issue_type: c.issue_type ?? "",
          story_points: c.story_points != null ? String(c.story_points) : "",
        })),
      );
      setDirty(false);
    }
  }, [serverConfigs]);

  // Filter only steps that have an earlier step to go back to
  const validSteps = steps.filter((_, i) => i > 0);

  const addRow = () => {
    if (validSteps.length === 0) return;
    setLocalConfigs((prev) => [
      ...prev,
      {
        from_step_id: validSteps[0].id,
        base_probability: "0.1",
        to_step_id: steps[0].id,
        issue_type: "",
        story_points: "",
      },
    ]);
    setDirty(true);
  };

  const removeRow = (index: number) => {
    setLocalConfigs((prev) => prev.filter((_, i) => i !== index));
    setDirty(true);
  };

  const updateRow = (
    index: number,
    field: keyof LocalConfig,
    value: string | number | null,
  ) => {
    setLocalConfigs((prev) =>
      prev.map((c, i) => (i === index ? { ...c, [field]: value } : c)),
    );
    setDirty(true);
  };

  const handleSave = () => {
    const configs: MoveLeftConfigInput[] = localConfigs
      .filter((c) => c.from_step_id && parseFloat(c.base_probability) > 0)
      .map((c) => ({
        from_step_id: c.from_step_id,
        base_probability: parseFloat(c.base_probability),
        issue_type: c.issue_type || null,
        story_points: c.story_points ? parseInt(c.story_points, 10) : null,
        targets: c.to_step_id
          ? [{ to_step_id: c.to_step_id, weight: 1.0 }]
          : [],
      }));
    replaceMutation.mutate(configs, {
      onSuccess: () => setDirty(false),
    });
  };

  if (steps.length < 2) {
    return (
      <p className="text-sm text-muted-foreground">
        Add at least 2 workflow steps to configure move-left rules.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Move-Left Rules</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={addRow}>
            + Add Rule
          </Button>
          <Button
            size="sm"
            disabled={!dirty || replaceMutation.isPending}
            onClick={handleSave}
            className="relative"
          >
            {replaceMutation.isPending ? "Saving..." : "Save Rules"}
            {dirty && (
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-orange-500" />
            )}
          </Button>
        </div>
      </div>

      {localConfigs.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No move-left rules configured. Items always move forward.
        </p>
      ) : (
        <div className="space-y-2">
          {/* Header */}
          <div className="flex items-center gap-2 px-2 text-xs font-medium text-muted-foreground">
            <span className="w-8" />
            <span className="w-36">From Status</span>
            <span className="w-4" />
            <span className="w-36">To Status</span>
            <span className="w-16">Prob.</span>
            <span className="w-28">Issue Type</span>
            <span className="w-20">Size (SP)</span>
            <span className="w-8" />
          </div>

          {localConfigs.map((config, i) => (
            <div
              key={i}
              className="flex items-center gap-2 rounded-md border p-2 text-sm"
            >
              <span className="w-8 shrink-0 text-muted-foreground">From</span>
              <Select
                value={String(config.from_step_id)}
                onValueChange={(v) =>
                  v && updateRow(i, "from_step_id", parseInt(v, 10))
                }
              >
                <SelectTrigger className="h-8 w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {validSteps.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.jira_status}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <span className="w-4 shrink-0 text-center text-muted-foreground">
                →
              </span>

              <Select
                value={config.to_step_id ? String(config.to_step_id) : ""}
                onValueChange={(v) =>
                  v && updateRow(i, "to_step_id", parseInt(v, 10))
                }
              >
                <SelectTrigger className="h-8 w-36">
                  <SelectValue placeholder="Target step" />
                </SelectTrigger>
                <SelectContent>
                  {steps
                    .filter(
                      (s) =>
                        s.order <
                        (steps.find((st) => st.id === config.from_step_id)
                          ?.order ?? 999),
                    )
                    .map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        {s.jira_status}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>

              <Input
                type="number"
                min="0"
                max="1"
                step="0.05"
                className="h-8 w-16 text-center text-sm"
                value={config.base_probability}
                onChange={(e) =>
                  updateRow(i, "base_probability", e.target.value)
                }
                title="Probability (0.0–1.0)"
              />

              <Select
                value={config.issue_type || "__all__"}
                onValueChange={(v) =>
                  updateRow(i, "issue_type", v === "__all__" ? "" : v)
                }
              >
                <SelectTrigger className="h-8 w-28">
                  <SelectValue placeholder="All types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All types</SelectItem>
                  {ISSUE_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={config.story_points || "__all__"}
                onValueChange={(v) =>
                  updateRow(i, "story_points", v === "__all__" ? "" : v)
                }
              >
                <SelectTrigger className="h-8 w-20">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All</SelectItem>
                  {STORY_POINTS.map((sp) => (
                    <SelectItem key={sp} value={String(sp)}>
                      {sp} SP
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 shrink-0 px-2 text-muted-foreground hover:text-destructive"
                onClick={() => removeRow(i)}
              >
                ×
              </Button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Rules are matched most-specific first: a rule with both issue type and
        size takes priority over a generic rule. Leave filters blank to apply to
        all items.
      </p>
    </div>
  );
}
