import { useCallback, useEffect, useMemo, useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Button } from "@/components/ui/button";
import { useJiraStatuses } from "@/hooks/useJiraStatuses";
import { useReplaceWorkflow, useWorkflow } from "@/hooks/useWorkflow";
import type { PreviewConfigItem, TouchTimeConfigInput, WorkflowStep, WorkflowStepInput } from "@/lib/types";
import { StatusDistributionChart } from "@/components/templates/StatusDistributionChart";
import { AddStepModal } from "./AddStepModal";
import { MoveLeftGrid } from "./MoveLeftGrid";
import { StepRow } from "./StepRow";
import { TouchTimeTree } from "./TouchTimeTree";

interface WorkflowDesignerProps {
  teamId: number;
  projectKey: string;
}

export function WorkflowDesigner({ teamId, projectKey }: WorkflowDesignerProps) {
  const { data: workflow } = useWorkflow(teamId);
  const replaceWorkflow = useReplaceWorkflow(teamId);
  const { data: jiraStatuses = [] } = useJiraStatuses(projectKey);

  const [localSteps, setLocalSteps] = useState<WorkflowStep[]>([]);
  const [localTouchTimes, setLocalTouchTimes] = useState<
    Record<number, TouchTimeConfigInput[]>
  >({});
  const [dirty, setDirty] = useState(false);
  const [addStepOpen, setAddStepOpen] = useState(false);

  // Sync from server
  useEffect(() => {
    if (workflow?.steps) {
      setLocalSteps(workflow.steps);
      const ttMap: Record<number, TouchTimeConfigInput[]> = {};
      for (const step of workflow.steps) {
        ttMap[step.id] = step.touch_time_configs.map((c) => ({
          issue_type: c.issue_type,
          story_points: c.story_points,
          min_hours: c.min_hours,
          max_hours: c.max_hours,
          full_time_p25: c.full_time_p25,
          full_time_p50: c.full_time_p50,
          full_time_p99: c.full_time_p99,
        }));
      }
      setLocalTouchTimes(ttMap);
      setDirty(false);
    }
  }, [workflow]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (!over || active.id === over.id) return;

      setLocalSteps((prev) => {
        const oldIndex = prev.findIndex((s) => s.id === active.id);
        const newIndex = prev.findIndex((s) => s.id === over.id);
        const next = [...prev];
        const [removed] = next.splice(oldIndex, 1);
        next.splice(newIndex, 0, removed);
        return next.map((s, i) => ({ ...s, order: i }));
      });
      setDirty(true);
    },
    [],
  );

  const handleSave = () => {
    const steps: WorkflowStepInput[] = localSteps.map((s) => ({
      jira_status: s.jira_status,
      role_required: s.role_required,
      roles_json: s.roles_json,
      order: s.order,
      max_wait_hours: s.max_wait_hours,
      wip_contribution: s.wip_contribution,
      status_category: s.status_category,
      touch_time_configs: localTouchTimes[s.id] ?? [],
    }));
    replaceWorkflow.mutate(steps);
    setDirty(false);
  };

  const handleUpdateStep = (stepId: number, updates: Partial<WorkflowStep>) => {
    setLocalSteps((prev) =>
      prev.map((s) => (s.id === stepId ? { ...s, ...updates } : s)),
    );
    setDirty(true);
  };

  const handleDeleteStep = (stepId: number) => {
    setLocalSteps((prev) => prev.filter((s) => s.id !== stepId));
    setDirty(true);
  };

  const handleTouchTimesChangeAll = (newTouchTimes: Record<number, TouchTimeConfigInput[]>) => {
    setLocalTouchTimes(newTouchTimes);
    setDirty(true);
  };

  // Build PreviewConfigItem[] for the status distribution chart
  const statusDistributionConfigs = useMemo<PreviewConfigItem[]>(() => {
    const configs: PreviewConfigItem[] = [];
    for (const step of localSteps) {
      // Infer status_category when not set (same logic as backend)
      let cat = step.status_category;
      if (!cat) {
        const idx = localSteps.indexOf(step);
        if (idx === 0) cat = "todo";
        else if (idx === localSteps.length - 1) cat = "done";
        else cat = "in_progress";
      }

      const ttConfigs = localTouchTimes[step.id] ?? [];
      for (const tt of ttConfigs) {
        configs.push({
          workflow_step_id: step.id,
          jira_status: step.jira_status,
          status_category: cat,
          issue_type: tt.issue_type,
          story_points: tt.story_points,
          min_hours: tt.min_hours,
          max_hours: tt.max_hours,
          full_time_p25: tt.full_time_p25 ?? null,
          full_time_p50: tt.full_time_p50 ?? null,
          full_time_p99: tt.full_time_p99 ?? null,
        });
      }
    }
    return configs;
  }, [localSteps, localTouchTimes]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Workflow Steps</h2>
        <div className="flex gap-2">
          <Button
            onClick={() => setAddStepOpen(true)}
            variant="outline"
            size="sm"
            data-testid="add-step-btn"
          >
            + Add Step
          </Button>
          <Button
            onClick={handleSave}
            size="sm"
            disabled={!dirty}
            className="relative"
            data-testid="save-workflow-btn"
          >
            Save
            {dirty && (
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-orange-500" />
            )}
          </Button>
        </div>
      </div>

      {localSteps.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
          No workflow steps yet
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={localSteps.map((s) => s.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="space-y-3" data-testid="step-list">
              {localSteps.map((step) => (
                <StepRow
                  key={step.id}
                  step={step}
                  jiraStatuses={jiraStatuses}
                  onDelete={() => handleDeleteStep(step.id)}
                  onUpdate={(updates) => handleUpdateStep(step.id, updates)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      <AddStepModal
        open={addStepOpen}
        onClose={() => setAddStepOpen(false)}
        onSubmit={(data) => {
          // Optimistically add a temporary step
          const tempStep: WorkflowStep = {
            id: -Date.now(),
            workflow_id: workflow?.id ?? 0,
            jira_status: data.jira_status,
            role_required: data.role_required,
            roles_json: data.roles_json ?? null,
            order: data.order,
            max_wait_hours: data.max_wait_hours ?? 24,
            wip_contribution: data.wip_contribution ?? 1,
            status_category: data.status_category ?? null,
            touch_time_configs: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
          setLocalSteps((prev) => [...prev, tempStep]);
          setDirty(true);
        }}
        projectKey={projectKey}
        nextOrder={localSteps.length}
      />

      {/* Touch time configuration — hierarchical by issue type */}
      {localSteps.length > 0 && (
        <div className="mt-6 border-t pt-6">
          <h2 className="mb-3 text-lg font-semibold">Timing Configuration</h2>
          <TouchTimeTree
            steps={localSteps}
            touchTimes={localTouchTimes}
            onChange={handleTouchTimesChangeAll}
          />
        </div>
      )}

      {/* Status distribution chart — shows expected time in status */}
      {statusDistributionConfigs.length > 0 && (
        <div className="mt-6 border-t pt-6">
          <StatusDistributionChart configs={statusDistributionConfigs} />
        </div>
      )}

      {/* Move-left configuration — only show when steps are saved */}
      {workflow?.steps && workflow.steps.length >= 2 && (
        <div className="mt-6 border-t pt-6">
          <MoveLeftGrid teamId={teamId} steps={workflow.steps} />
        </div>
      )}
    </div>
  );
}
