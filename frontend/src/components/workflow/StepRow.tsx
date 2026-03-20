import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BrokenStepBadge } from "@/components/shared/BrokenStepBadge";
import { getRoleColor } from "@/lib/roles";
import type { JiraStatus, TouchTimeConfigInput, WorkflowStep } from "@/lib/types";
import { TouchTimeGrid } from "./TouchTimeGrid";

interface StepRowProps {
  step: WorkflowStep;
  jiraStatuses: JiraStatus[];
  touchTimeConfigs: TouchTimeConfigInput[];
  onTouchTimeChange: (configs: TouchTimeConfigInput[]) => void;
  onDelete: () => void;
}

export function StepRow({
  step,
  jiraStatuses,
  touchTimeConfigs,
  onTouchTimeChange,
  onDelete,
}: StepRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: step.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const roleColor = getRoleColor(step.role_required);
  const statusKnown = jiraStatuses.some((s) => s.name === step.jira_status);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="rounded-lg border bg-card p-4 shadow-sm"
      data-testid={`step-row-${step.id}`}
    >
      <div className="mb-3 flex items-center gap-3">
        <button
          className="cursor-grab touch-none text-muted-foreground hover:text-foreground"
          {...attributes}
          {...listeners}
          data-testid="drag-handle"
        >
          &#x2807;
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{step.jira_status}</span>
            {!statusKnown && jiraStatuses.length > 0 && <BrokenStepBadge />}
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {step.roles_json ? (
              JSON.parse(step.roles_json).map((r: string) => {
                const rc = getRoleColor(r);
                return (
                  <Badge
                    key={r}
                    variant="outline"
                    className={`${rc.bg} ${rc.text} border ${rc.border}`}
                  >
                    {r}
                  </Badge>
                );
              })
            ) : (
              <Badge
                variant="outline"
                className={`${roleColor.bg} ${roleColor.text} border ${roleColor.border}`}
              >
                {step.role_required}
              </Badge>
            )}
            <span>· max wait {step.max_wait_hours}h</span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onDelete}
          data-testid={`delete-step-${step.id}`}
        >
          Delete
        </Button>
      </div>
      <TouchTimeGrid configs={touchTimeConfigs} onChange={onTouchTimeChange} />
    </div>
  );
}
