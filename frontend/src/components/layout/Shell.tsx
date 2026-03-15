import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export type Section =
  | "workflow"
  | "members"
  | "dysfunctions"
  | "dependencies"
  | "simulation";

interface ShellProps {
  activeTeamId: number | null;
  activeTeamName: string;
  activeSection: Section;
  onTeamSwitch: (teamId: number) => void;
  onSectionSwitch: (section: Section) => void;
  onAddTeam: () => void;
  onAction?: () => void;
  actionLabel?: string;
  dirty?: boolean;
  children: ReactNode;
}

export function Shell({
  activeTeamId,
  activeTeamName,
  activeSection,
  onTeamSwitch,
  onSectionSwitch,
  onAddTeam,
  onAction,
  actionLabel,
  dirty,
  children,
}: ShellProps) {
  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        activeTeamId={activeTeamId}
        activeSection={activeSection}
        onTeamSwitch={onTeamSwitch}
        onSectionSwitch={onSectionSwitch}
        onAddTeam={onAddTeam}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar
          teamName={activeTeamName}
          section={activeSection}
          onAction={onAction}
          actionLabel={actionLabel}
          dirty={dirty}
        />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
