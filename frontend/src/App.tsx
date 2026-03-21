import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddTeamModal } from "@/components/layout/AddTeamModal";
import { Shell } from "@/components/layout/Shell";
import type { Section } from "@/components/layout/Shell";
import { DependencyConfig } from "@/components/dependencies/DependencyConfig";
import { MemberTable } from "@/components/members/MemberTable";
import { TeamSettings } from "@/components/settings/TeamSettings";
import { SimulationDashboard } from "@/components/simulation/SimulationDashboard";
import { WorkflowDesigner } from "@/components/workflow/WorkflowDesigner";
import { TemplatePage } from "@/components/templates/TemplatePage";
import { useCreateTeam, useTeams } from "@/hooks/useTeams";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function AppContent() {
  const { data: teams = [] } = useTeams();
  const createTeam = useCreateTeam();
  const [activeTeamId, setActiveTeamId] = useState<number | null>(null);
  const [activeSection, setActiveSection] = useState<Section>("workflow");
  const [addTeamOpen, setAddTeamOpen] = useState(false);

  const activeTeam = teams.find((t) => t.id === activeTeamId);

  // Auto-select first team when teams load and none selected
  if (teams.length > 0 && activeTeamId === null) {
    setActiveTeamId(teams[0].id);
  }

  return (
    <>
      <Shell
        activeTeamId={activeTeamId}
        activeTeamName={activeTeam?.name ?? ""}
        activeSection={activeSection}
        onTeamSwitch={setActiveTeamId}
        onSectionSwitch={setActiveSection}
        onAddTeam={() => setAddTeamOpen(true)}
      >
        {activeTeamId ? (
          <SectionContent
            teamId={activeTeamId}
            section={activeSection}
            projectKey={activeTeam?.jira_project_key ?? ""}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Create a team to get started
          </div>
        )}
      </Shell>
      <AddTeamModal
        open={addTeamOpen}
        onClose={() => setAddTeamOpen(false)}
        onSubmit={(data) => {
          createTeam.mutate(data, {
            onSuccess: (team) => {
              setActiveTeamId(team.id);
              setAddTeamOpen(false);
            },
          });
        }}
        loading={createTeam.isPending}
      />
    </>
  );
}

function SectionContent({
  teamId,
  section,
  projectKey,
}: {
  teamId: number;
  section: Section;
  projectKey: string;
}) {
  switch (section) {
    case "workflow":
      return <WorkflowDesigner teamId={teamId} projectKey={projectKey} />;
    case "members":
      return <MemberTable teamId={teamId} />;
    case "settings":
      return <TeamSettings teamId={teamId} />;
    case "dependencies":
      return <DependencyConfig />;
    case "simulation":
      return <SimulationDashboard />;
    case "templates":
      return <TemplatePage />;
  }
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
