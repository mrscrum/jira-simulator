import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useCreateDependency,
  useDeleteDependency,
  useDependencies,
} from "@/hooks/useDependencies";
import { useTeams } from "@/hooks/useTeams";

const DEPENDENCY_TYPES = [
  "blocks",
  "shared component",
  "cross-team handoff",
  "cross-team bug",
];

export function DependencyConfig() {
  const { data: deps = [] } = useDependencies();
  const { data: teams = [] } = useTeams();
  const createDep = useCreateDependency();
  const deleteDep = useDeleteDependency();

  const [sourceId, setSourceId] = useState<string>("");
  const [targetId, setTargetId] = useState<string>("");
  const [depType, setDepType] = useState<string>("");
  const [error, setError] = useState<string>("");

  const handleAdd = () => {
    setError("");
    if (!sourceId || !targetId || !depType) return;
    if (sourceId === targetId) {
      setError("Source and target team must differ");
      return;
    }
    const duplicate = deps.some(
      (d) =>
        d.source_team_id === parseInt(sourceId) &&
        d.target_team_id === parseInt(targetId) &&
        d.dependency_type === depType,
    );
    if (duplicate) {
      setError("This dependency already exists");
      return;
    }
    createDep.mutate(
      {
        source_team_id: parseInt(sourceId),
        target_team_id: parseInt(targetId),
        dependency_type: depType,
      },
      {
        onSuccess: () => {
          setSourceId("");
          setTargetId("");
          setDepType("");
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Cross-Team Dependencies</h2>

      {deps.length === 0 && (
        <div className="mb-4 flex h-20 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
          No dependencies configured
        </div>
      )}

      <div className="space-y-2">
        {deps.map((dep) => {
          const source = teams.find((t) => t.id === dep.source_team_id);
          const target = teams.find((t) => t.id === dep.target_team_id);
          return (
            <div
              key={dep.id}
              className="flex items-center gap-2 rounded-md border p-2"
              data-testid={`dep-row-${dep.id}`}
            >
              <span className="font-medium">{source?.name ?? dep.source_team_id}</span>
              <span className="text-sm text-muted-foreground">{dep.dependency_type}</span>
              <span className="text-muted-foreground">&rarr;</span>
              <span className="font-medium">{target?.name ?? dep.target_team_id}</span>
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto"
                onClick={() => deleteDep.mutate(dep.id)}
                data-testid={`delete-dep-${dep.id}`}
              >
                Remove
              </Button>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-end gap-2">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Team A</label>
          <Select value={sourceId} onValueChange={(v) => v && setSourceId(v)}>
            <SelectTrigger className="w-36" data-testid="dep-source-select">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {teams.map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Type</label>
          <Select value={depType} onValueChange={(v) => v && setDepType(v)}>
            <SelectTrigger className="w-44" data-testid="dep-type-select">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {DEPENDENCY_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <span className="pb-2 text-muted-foreground">&rarr;</span>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Team B</label>
          <Select value={targetId} onValueChange={(v) => v && setTargetId(v)}>
            <SelectTrigger className="w-36" data-testid="dep-target-select">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {teams
                .filter((t) => String(t.id) !== sourceId)
                .map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.name}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={handleAdd} size="sm" data-testid="add-dep-btn">
          + Add
        </Button>
      </div>
      {error && (
        <p className="mt-2 text-sm text-destructive" data-testid="dep-error">
          {error}
        </p>
      )}
    </div>
  );
}
