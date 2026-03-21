import { useCallback, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { TouchTimeConfigInput, WorkflowStep } from "@/lib/types";

const COMMON_SIZES = [0, 1, 2, 3, 5, 8, 13];

interface TouchTimeTreeProps {
  steps: WorkflowStep[];
  touchTimes: Record<number, TouchTimeConfigInput[]>;
  onChange: (touchTimes: Record<number, TouchTimeConfigInput[]>) => void;
}

type ConfigField = keyof Pick<
  TouchTimeConfigInput,
  "min_hours" | "max_hours" | "full_time_p25" | "full_time_p50" | "full_time_p99"
>;

/** Derive which issue types, sizes, and statuses exist from flat configs. */
function deriveStructure(touchTimes: Record<number, TouchTimeConfigInput[]>) {
  const issueTypes = new Set<string>();
  const sizesPerType = new Map<string, Set<number>>();
  // key = "type:size" → Set<stepId>
  const stepsPerTypeSize = new Map<string, Set<number>>();

  for (const [stepIdStr, configs] of Object.entries(touchTimes)) {
    const stepId = Number(stepIdStr);
    for (const cfg of configs) {
      issueTypes.add(cfg.issue_type);
      if (!sizesPerType.has(cfg.issue_type)) sizesPerType.set(cfg.issue_type, new Set());
      sizesPerType.get(cfg.issue_type)!.add(cfg.story_points);
      const key = `${cfg.issue_type}:${cfg.story_points}`;
      if (!stepsPerTypeSize.has(key)) stepsPerTypeSize.set(key, new Set());
      stepsPerTypeSize.get(key)!.add(stepId);
    }
  }

  return {
    issueTypes: Array.from(issueTypes).sort(),
    sizesPerType,
    stepsPerTypeSize,
  };
}

export function TouchTimeTree({ steps, touchTimes, onChange }: TouchTimeTreeProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [newTypeName, setNewTypeName] = useState("");
  const [addingSizeTo, setAddingSizeTo] = useState<string | null>(null);
  const [newSizeValue, setNewSizeValue] = useState("");

  const structure = useMemo(() => deriveStructure(touchTimes), [touchTimes]);

  const toggle = (key: string) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  const getConfig = useCallback(
    (stepId: number, issueType: string, sp: number) =>
      touchTimes[stepId]?.find(
        (c) => c.issue_type === issueType && c.story_points === sp,
      ),
    [touchTimes],
  );

  const updateField = useCallback(
    (stepId: number, issueType: string, sp: number, field: ConfigField, value: string) => {
      const num = parseFloat(value) || 0;
      const stepConfigs = touchTimes[stepId] ?? [];
      const existing = stepConfigs.find(
        (c) => c.issue_type === issueType && c.story_points === sp,
      );
      let updated: TouchTimeConfigInput[];
      if (existing) {
        updated = stepConfigs.map((c) =>
          c.issue_type === issueType && c.story_points === sp
            ? { ...c, [field]: num }
            : c,
        );
      } else {
        updated = [
          ...stepConfigs,
          {
            issue_type: issueType,
            story_points: sp,
            min_hours: field === "min_hours" ? num : 0,
            max_hours: field === "max_hours" ? num : 0,
            full_time_p25: field === "full_time_p25" ? num : null,
            full_time_p50: field === "full_time_p50" ? num : null,
            full_time_p99: field === "full_time_p99" ? num : null,
          },
        ];
      }
      onChange({ ...touchTimes, [stepId]: updated });
    },
    [touchTimes, onChange],
  );

  // --- Mutations ---

  const addIssueType = (name: string) => {
    if (!name.trim() || structure.issueTypes.includes(name.trim())) return;
    const type = name.trim();
    // Add default (0 SP) config to first step
    if (steps.length === 0) return;
    const firstStepId = steps[0].id;
    const stepConfigs = touchTimes[firstStepId] ?? [];
    const newConfig: TouchTimeConfigInput = {
      issue_type: type,
      story_points: 0,
      min_hours: 1,
      max_hours: 2,
      full_time_p25: null,
      full_time_p50: 1.5,
      full_time_p99: null,
    };
    onChange({ ...touchTimes, [firstStepId]: [...stepConfigs, newConfig] });
    setNewTypeName("");
  };

  const removeIssueType = (type: string) => {
    const next: Record<number, TouchTimeConfigInput[]> = {};
    for (const [sid, cfgs] of Object.entries(touchTimes)) {
      next[Number(sid)] = cfgs.filter((c) => c.issue_type !== type);
    }
    onChange(next);
  };

  const addSize = (type: string, sp: number) => {
    // Add this size to all steps that already have configs for this issue type
    const key0 = `${type}:${Array.from(structure.sizesPerType.get(type) ?? [0])[0]}`;
    const existingStepIds = structure.stepsPerTypeSize.get(key0) ?? new Set();
    // If no steps yet, use all steps
    const stepIds = existingStepIds.size > 0 ? existingStepIds : new Set(steps.map((s) => s.id));

    const next = { ...touchTimes };
    for (const stepId of stepIds) {
      const stepConfigs = next[stepId] ?? [];
      if (!stepConfigs.some((c) => c.issue_type === type && c.story_points === sp)) {
        next[stepId] = [
          ...stepConfigs,
          {
            issue_type: type,
            story_points: sp,
            min_hours: 1,
            max_hours: 2,
            full_time_p25: null,
            full_time_p50: 1.5,
            full_time_p99: null,
          },
        ];
      }
    }
    onChange(next);
    setAddingSizeTo(null);
    setNewSizeValue("");
  };

  const removeSize = (type: string, sp: number) => {
    const next: Record<number, TouchTimeConfigInput[]> = {};
    for (const [sid, cfgs] of Object.entries(touchTimes)) {
      next[Number(sid)] = cfgs.filter(
        (c) => !(c.issue_type === type && c.story_points === sp),
      );
    }
    onChange(next);
  };

  const addStatusToTypeSize = (type: string, sp: number, stepId: number) => {
    const stepConfigs = touchTimes[stepId] ?? [];
    if (stepConfigs.some((c) => c.issue_type === type && c.story_points === sp)) return;
    onChange({
      ...touchTimes,
      [stepId]: [
        ...stepConfigs,
        {
          issue_type: type,
          story_points: sp,
          min_hours: 1,
          max_hours: 2,
          full_time_p25: null,
          full_time_p50: 1.5,
          full_time_p99: null,
        },
      ],
    });
  };

  const removeStatusFromTypeSize = (type: string, sp: number, stepId: number) => {
    const stepConfigs = touchTimes[stepId] ?? [];
    onChange({
      ...touchTimes,
      [stepId]: stepConfigs.filter(
        (c) => !(c.issue_type === type && c.story_points === sp),
      ),
    });
  };

  // Quick-add: add all statuses to an issue type + size
  const addAllStatuses = (type: string, sp: number) => {
    const next = { ...touchTimes };
    for (const step of steps) {
      const stepConfigs = next[step.id] ?? [];
      if (!stepConfigs.some((c) => c.issue_type === type && c.story_points === sp)) {
        next[step.id] = [
          ...stepConfigs,
          {
            issue_type: type,
            story_points: sp,
            min_hours: 1,
            max_hours: 2,
            full_time_p25: null,
            full_time_p50: 1.5,
            full_time_p99: null,
          },
        ];
      }
    }
    onChange(next);
  };

  const stepById = useMemo(() => {
    const m = new Map<number, WorkflowStep>();
    for (const s of steps) m.set(s.id, s);
    return m;
  }, [steps]);

  // Sort step IDs by step order
  const sortedStepIds = useMemo(() => steps.map((s) => s.id), [steps]);

  const sizeLabel = (sp: number) => (sp === 0 ? "Default" : `${sp} SP`);

  return (
    <div className="space-y-3" data-testid="touch-time-tree">
      {structure.issueTypes.length === 0 && (
        <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
          No timing configurations yet. Add an issue type to get started.
        </div>
      )}

      {structure.issueTypes.map((type) => {
        const typeCollapsed = collapsed[type];
        const sizes = Array.from(structure.sizesPerType.get(type) ?? []).sort(
          (a, b) => a - b,
        );

        return (
          <div key={type} className="rounded-lg border bg-card">
            {/* Issue Type Header */}
            <div className="flex items-center gap-2 border-b px-3 py-2">
              <button
                className="text-xs text-muted-foreground"
                onClick={() => toggle(type)}
              >
                {typeCollapsed ? "▶" : "▼"}
              </button>
              <span className="font-semibold">{type}</span>
              <div className="ml-2 flex flex-wrap gap-1">
                {sizes.map((sp) => (
                  <Badge
                    key={sp}
                    variant="secondary"
                    className="cursor-pointer text-[10px]"
                    onClick={() => toggle(`${type}:${sp}`)}
                  >
                    {sizeLabel(sp)}
                  </Badge>
                ))}
              </div>
              <div className="ml-auto flex items-center gap-1">
                {addingSizeTo === type ? (
                  <div className="flex items-center gap-1">
                    <div className="flex flex-wrap gap-1">
                      {COMMON_SIZES.filter((s) => !sizes.includes(s)).map(
                        (s) => (
                          <button
                            key={s}
                            className="rounded border px-1.5 py-0.5 text-[10px] hover:bg-accent"
                            onClick={() => addSize(type, s)}
                          >
                            {sizeLabel(s)}
                          </button>
                        ),
                      )}
                    </div>
                    <Input
                      type="number"
                      min="0"
                      className="h-6 w-14 px-1 text-xs"
                      placeholder="SP"
                      value={newSizeValue}
                      onChange={(e) => setNewSizeValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && newSizeValue) {
                          addSize(type, parseInt(newSizeValue, 10));
                        }
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-1 text-xs"
                      onClick={() => setAddingSizeTo(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => setAddingSizeTo(type)}
                  >
                    + Size
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs text-destructive hover:text-destructive"
                  onClick={() => removeIssueType(type)}
                >
                  Remove
                </Button>
              </div>
            </div>

            {/* Sizes */}
            {!typeCollapsed && (
              <div className="divide-y">
                {sizes.map((sp) => {
                  const sizeKey = `${type}:${sp}`;
                  const sizeCollapsed = collapsed[sizeKey];
                  const activeStepIds = Array.from(
                    structure.stepsPerTypeSize.get(sizeKey) ?? [],
                  ).sort(
                    (a, b) =>
                      sortedStepIds.indexOf(a) - sortedStepIds.indexOf(b),
                  );
                  const availableSteps = steps.filter(
                    (s) => !activeStepIds.includes(s.id),
                  );

                  return (
                    <div key={sp} className="pl-6">
                      {/* Size Header */}
                      <div className="flex items-center gap-2 py-1.5 pr-3">
                        <button
                          className="text-xs text-muted-foreground"
                          onClick={() => toggle(sizeKey)}
                        >
                          {sizeCollapsed ? "▶" : "▼"}
                        </button>
                        <span className="text-sm font-medium">
                          {sizeLabel(sp)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          ({activeStepIds.length} status
                          {activeStepIds.length !== 1 ? "es" : ""})
                        </span>
                        <div className="ml-auto flex items-center gap-1">
                          {activeStepIds.length < steps.length && (
                            <AddStatusDropdown
                              availableSteps={availableSteps}
                              onAdd={(stepId) =>
                                addStatusToTypeSize(type, sp, stepId)
                              }
                              onAddAll={() => addAllStatuses(type, sp)}
                            />
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-5 px-1 text-[10px] text-destructive hover:text-destructive"
                            onClick={() => removeSize(type, sp)}
                          >
                            ×
                          </Button>
                        </div>
                      </div>

                      {/* Status rows */}
                      {!sizeCollapsed && activeStepIds.length > 0 && (
                        <div className="mb-2 mr-3">
                          {/* Header */}
                          <div className="grid grid-cols-[minmax(70px,1fr)_50px_50px_50px_50px_50px_16px] gap-1 px-2 pb-1 text-[10px] text-muted-foreground">
                            <span>Status</span>
                            <span className="text-center">Work min</span>
                            <span className="text-center">Work max</span>
                            <span className="text-center text-blue-600">
                              p25
                            </span>
                            <span className="text-center text-blue-600">
                              p50
                            </span>
                            <span className="text-center text-blue-600">
                              p99
                            </span>
                            <span />
                          </div>
                          {/* Rows */}
                          {activeStepIds.map((stepId) => {
                            const step = stepById.get(stepId);
                            if (!step) return null;
                            const cfg = getConfig(stepId, type, sp);
                            return (
                              <div
                                key={stepId}
                                className="grid grid-cols-[minmax(70px,1fr)_50px_50px_50px_50px_50px_16px] items-center gap-1 px-2 py-0.5"
                              >
                                <span className="truncate text-xs">
                                  {step.jira_status}
                                </span>
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.5"
                                  className="h-6 px-1 text-center text-xs"
                                  value={cfg?.min_hours ?? ""}
                                  onChange={(e) =>
                                    updateField(
                                      stepId,
                                      type,
                                      sp,
                                      "min_hours",
                                      e.target.value,
                                    )
                                  }
                                  placeholder="0"
                                />
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.5"
                                  className="h-6 px-1 text-center text-xs"
                                  value={cfg?.max_hours ?? ""}
                                  onChange={(e) =>
                                    updateField(
                                      stepId,
                                      type,
                                      sp,
                                      "max_hours",
                                      e.target.value,
                                    )
                                  }
                                  placeholder="0"
                                />
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.5"
                                  className="h-6 px-1 text-center text-xs text-blue-600"
                                  value={cfg?.full_time_p25 ?? ""}
                                  onChange={(e) =>
                                    updateField(
                                      stepId,
                                      type,
                                      sp,
                                      "full_time_p25",
                                      e.target.value,
                                    )
                                  }
                                  placeholder="—"
                                />
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.5"
                                  className="h-6 px-1 text-center text-xs text-blue-600"
                                  value={cfg?.full_time_p50 ?? ""}
                                  onChange={(e) =>
                                    updateField(
                                      stepId,
                                      type,
                                      sp,
                                      "full_time_p50",
                                      e.target.value,
                                    )
                                  }
                                  placeholder="—"
                                />
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.5"
                                  className="h-6 px-1 text-center text-xs text-blue-600"
                                  value={cfg?.full_time_p99 ?? ""}
                                  onChange={(e) =>
                                    updateField(
                                      stepId,
                                      type,
                                      sp,
                                      "full_time_p99",
                                      e.target.value,
                                    )
                                  }
                                  placeholder="—"
                                />
                                <button
                                  className="text-xs text-muted-foreground hover:text-destructive"
                                  onClick={() =>
                                    removeStatusFromTypeSize(type, sp, stepId)
                                  }
                                  title="Remove this status"
                                >
                                  ×
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {!sizeCollapsed && activeStepIds.length === 0 && (
                        <div className="mb-2 px-2 text-xs text-muted-foreground">
                          No statuses configured.{" "}
                          <button
                            className="text-blue-600 hover:underline"
                            onClick={() => addAllStatuses(type, sp)}
                          >
                            Add all statuses
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      {/* Add Issue Type */}
      <div className="flex items-center gap-2">
        <Input
          className="h-8 w-40 text-sm"
          placeholder="New issue type..."
          value={newTypeName}
          onChange={(e) => setNewTypeName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") addIssueType(newTypeName);
          }}
        />
        <Button
          variant="outline"
          size="sm"
          className="h-8"
          disabled={!newTypeName.trim()}
          onClick={() => addIssueType(newTypeName)}
        >
          + Add Issue Type
        </Button>
        {structure.issueTypes.length === 0 && (
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => {
              // Quick-start: add Story, Bug, Task with all steps and common sizes
              const types = ["Story", "Bug", "Task"];
              const sizes = [0, 1, 2, 3, 5, 8, 13];
              const next = { ...touchTimes };
              for (const step of steps) {
                const existing = next[step.id] ?? [];
                const toAdd: TouchTimeConfigInput[] = [];
                for (const type of types) {
                  for (const sp of sizes) {
                    if (
                      !existing.some(
                        (c) =>
                          c.issue_type === type && c.story_points === sp,
                      )
                    ) {
                      toAdd.push({
                        issue_type: type,
                        story_points: sp,
                        min_hours: 1,
                        max_hours: 2,
                        full_time_p25: null,
                        full_time_p50: 1.5,
                        full_time_p99: null,
                      });
                    }
                  }
                }
                next[step.id] = [...existing, ...toAdd];
              }
              onChange(next);
            }}
          >
            Quick Start (Story, Bug, Task)
          </Button>
        )}
      </div>

      <div className="text-[10px] text-muted-foreground">
        Work min/max: uniform distribution for active work hours.{" "}
        <span className="text-blue-600">
          p25/p50/p99: log-normal distribution for total time in status
          (includes wait).
        </span>{" "}
        Default (0 SP) is used as fallback when no size-specific config exists.
      </div>
    </div>
  );
}

/** Dropdown to add a status (workflow step) to an issue type + size. */
function AddStatusDropdown({
  availableSteps,
  onAdd,
  onAddAll,
}: {
  availableSteps: WorkflowStep[];
  onAdd: (stepId: number) => void;
  onAddAll: () => void;
}) {
  const [open, setOpen] = useState(false);

  if (availableSteps.length === 0) return null;

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        className="h-5 px-1 text-[10px]"
        onClick={() => setOpen(!open)}
      >
        + Status
      </Button>
      {open && (
        <div className="absolute right-0 top-full z-10 mt-1 min-w-[150px] rounded border bg-popover p-1 shadow-md">
          <button
            className="w-full rounded px-2 py-1 text-left text-xs font-medium hover:bg-accent"
            onClick={() => {
              onAddAll();
              setOpen(false);
            }}
          >
            Add all remaining
          </button>
          <div className="my-1 border-t" />
          {availableSteps.map((step) => (
            <button
              key={step.id}
              className="w-full rounded px-2 py-1 text-left text-xs hover:bg-accent"
              onClick={() => {
                onAdd(step.id);
                setOpen(false);
              }}
            >
              {step.jira_status}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
