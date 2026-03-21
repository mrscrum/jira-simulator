import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BrokenStepBadge } from "@/components/shared/BrokenStepBadge";
import { getRoleColor } from "@/lib/roles";
import type { JiraStatus, WorkflowStep } from "@/lib/types";

interface StepRowProps {
  step: WorkflowStep;
  jiraStatuses: JiraStatus[];
  onDelete: () => void;
  onUpdate?: (updates: Partial<WorkflowStep>) => void;
}

export function StepRow({
  step,
  jiraStatuses,
  onDelete,
  onUpdate,
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
            {onUpdate && (
              <div className="ml-2 flex items-center gap-0.5">
                {(["todo", "in_progress", "done"] as const).map((cat) => (
                  <button
                    key={cat}
                    className={`rounded px-1.5 py-0.5 text-[10px] ${
                      step.status_category === cat
                        ? cat === "todo"
                          ? "bg-slate-200 text-slate-700 font-medium"
                          : cat === "in_progress"
                          ? "bg-blue-100 text-blue-700 font-medium"
                          : "bg-green-100 text-green-700 font-medium"
                        : "text-muted-foreground hover:bg-accent"
                    }`}
                    onClick={() => onUpdate({ status_category: cat })}
                  >
                    {cat === "todo" ? "To Do" : cat === "in_progress" ? "In Progress" : "Done"}
                  </button>
                ))}
              </div>
            )}
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
    </div>
  );
}
