import { useTeams } from "@/hooks/useTeams";
import type { Section } from "./Shell";

const NAV_ITEMS: { section: Section; label: string }[] = [
  { section: "workflow", label: "Workflow" },
  { section: "members", label: "Members" },
  { section: "settings", label: "Settings" },
  { section: "templates", label: "Templates" },
  { section: "dependencies", label: "Dependencies" },
  { section: "simulation", label: "Simulation" },
  { section: "schedule", label: "Schedule" },
];

const TEAM_COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-purple-500",
  "bg-cyan-500",
];

interface SidebarProps {
  activeTeamId: number | null;
  activeSection: Section;
  onTeamSwitch: (teamId: number) => void;
  onSectionSwitch: (section: Section) => void;
  onAddTeam: () => void;
}

export function Sidebar({
  activeTeamId,
  activeSection,
  onTeamSwitch,
  onSectionSwitch,
  onAddTeam,
}: SidebarProps) {
  const { data: teams = [] } = useTeams();

  return (
    <aside className="flex w-[220px] flex-col border-r bg-muted/30" data-testid="sidebar">
      <div className="flex-1 overflow-auto p-3">
        <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Teams
        </h2>
        <ul className="space-y-1">
          {teams.map((team, i) => (
            <li key={team.id}>
              <button
                onClick={() => onTeamSwitch(team.id)}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                  team.id === activeTeamId
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground hover:bg-accent/50"
                }`}
                data-testid={`team-${team.id}`}
              >
                <span
                  className={`h-2.5 w-2.5 rounded-full ${TEAM_COLORS[i % TEAM_COLORS.length]}`}
                />
                {team.name}
              </button>
            </li>
          ))}
        </ul>
        <button
          onClick={onAddTeam}
          className="mt-2 flex w-full items-center gap-2 rounded-md border border-dashed border-muted-foreground/30 px-2 py-1.5 text-sm text-muted-foreground hover:border-muted-foreground/60"
          data-testid="add-team-btn"
        >
          + Add team
        </button>
      </div>

      <div className="border-t p-3">
        <h2 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Sections
        </h2>
        <ul className="space-y-1">
          {NAV_ITEMS.map(({ section, label }) => (
            <li key={section}>
              <button
                onClick={() => onSectionSwitch(section)}
                className={`flex w-full rounded-md px-2 py-1.5 text-sm ${
                  section === activeSection
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground hover:bg-accent/50"
                }`}
                data-testid={`nav-${section}`}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
