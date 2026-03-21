import { Button } from "@/components/ui/button";
import type { Section } from "./Shell";

const SECTION_LABELS: Record<Section, string> = {
  workflow: "Workflow",
  members: "Members",
  settings: "Settings",
  dependencies: "Dependencies",
  simulation: "Simulation",
  templates: "Templates",
};

const SECTION_HINTS: Record<Section, string> = {
  workflow: "Drag to reorder steps · Configure touch times and move-left",
  members: "Manage team members and their capacities",
  settings: "Sprint capacity, working hours, and simulation parameters",
  templates: "Manage cycle-time templates and apply them to teams",
  dependencies: "Define cross-team dependency links",
  simulation: "Control the simulation engine",
};

interface TopbarProps {
  teamName: string;
  section: Section;
  onAction?: () => void;
  actionLabel?: string;
  dirty?: boolean;
}

export function Topbar({
  teamName,
  section,
  onAction,
  actionLabel,
  dirty,
}: TopbarProps) {
  return (
    <header className="flex items-center justify-between border-b px-6 py-3">
      <div>
        <h1 className="text-lg font-semibold" data-testid="topbar-title">
          {teamName ? `${teamName} \u2014 ${SECTION_LABELS[section]}` : "Select a team"}
        </h1>
        <p className="text-sm text-muted-foreground">{SECTION_HINTS[section]}</p>
      </div>
      <div className="flex items-center gap-2">
        {actionLabel && onAction && (
          <Button onClick={onAction} variant="outline" size="sm">
            {actionLabel}
          </Button>
        )}
        {dirty !== undefined && (
          <Button
            onClick={onAction}
            size="sm"
            className="relative"
            data-testid="save-btn"
          >
            Save
            {dirty && (
              <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-orange-500" />
            )}
          </Button>
        )}
      </div>
    </header>
  );
}
