import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useTeam, useUpdateTeam } from "@/hooks/useTeams";

interface TeamSettingsProps {
  teamId: number;
}

export function TeamSettings({ teamId }: TeamSettingsProps) {
  const { data: team } = useTeam(teamId);
  const updateTeam = useUpdateTeam();

  const [sprintLength, setSprintLength] = useState("10");
  const [capMin, setCapMin] = useState("20");
  const [capMax, setCapMax] = useState("40");
  const [priorityRandom, setPriorityRandom] = useState(false);
  const [workStart, setWorkStart] = useState("9");
  const [workEnd, setWorkEnd] = useState("17");
  const [timezone, setTimezone] = useState("UTC");
  const [tickDuration, setTickDuration] = useState("1.0");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (team) {
      setSprintLength(String(team.sprint_length_days));
      setCapMin(String(team.sprint_capacity_min));
      setCapMax(String(team.sprint_capacity_max));
      setPriorityRandom(team.priority_randomization);
      setWorkStart(String(team.working_hours_start));
      setWorkEnd(String(team.working_hours_end));
      setTimezone(team.timezone);
      setTickDuration(String(team.tick_duration_hours));
      setDirty(false);
    }
  }, [team]);

  const handleSave = () => {
    updateTeam.mutate(
      {
        id: teamId,
        data: {
          sprint_length_days: parseInt(sprintLength, 10),
          sprint_capacity_min: parseInt(capMin, 10),
          sprint_capacity_max: parseInt(capMax, 10),
          priority_randomization: priorityRandom,
          working_hours_start: parseInt(workStart, 10),
          working_hours_end: parseInt(workEnd, 10),
          timezone,
          tick_duration_hours: parseFloat(tickDuration),
        },
      },
      { onSuccess: () => setDirty(false) },
    );
  };

  const markDirty = () => setDirty(true);

  if (!team) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Team Settings</h2>
        <Button
          onClick={handleSave}
          size="sm"
          disabled={!dirty || updateTeam.isPending}
          className="relative"
        >
          {updateTeam.isPending ? "Saving..." : "Save"}
          {dirty && (
            <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-orange-500" />
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Sprint Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="sprint-length">Sprint Length (days)</Label>
              <Input
                id="sprint-length"
                type="number"
                min="1"
                max="30"
                value={sprintLength}
                onChange={(e) => { setSprintLength(e.target.value); markDirty(); }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cap-min">Capacity Min (SP)</Label>
              <Input
                id="cap-min"
                type="number"
                min="1"
                value={capMin}
                onChange={(e) => { setCapMin(e.target.value); markDirty(); }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cap-max">Capacity Max (SP)</Label>
              <Input
                id="cap-max"
                type="number"
                min="1"
                value={capMax}
                onChange={(e) => { setCapMax(e.target.value); markDirty(); }}
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Switch
              checked={priorityRandom}
              onCheckedChange={(v) => { setPriorityRandom(v); markDirty(); }}
              id="priority-random"
            />
            <Label htmlFor="priority-random">
              Priority Randomization
              <span className="ml-2 text-xs text-muted-foreground">
                Shuffle backlog order during sprint planning
              </span>
            </Label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Working Hours</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="work-start">Start Hour (0-23)</Label>
              <Input
                id="work-start"
                type="number"
                min="0"
                max="23"
                value={workStart}
                onChange={(e) => { setWorkStart(e.target.value); markDirty(); }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="work-end">End Hour (0-23)</Label>
              <Input
                id="work-end"
                type="number"
                min="0"
                max="23"
                value={workEnd}
                onChange={(e) => { setWorkEnd(e.target.value); markDirty(); }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input
                id="timezone"
                value={timezone}
                onChange={(e) => { setTimezone(e.target.value); markDirty(); }}
                placeholder="UTC"
              />
            </div>
          </div>
          <div className="max-w-[200px] space-y-2">
            <Label htmlFor="tick-duration">Tick Duration (hours)</Label>
            <Input
              id="tick-duration"
              type="number"
              min="0.25"
              step="0.25"
              value={tickDuration}
              onChange={(e) => { setTickDuration(e.target.value); markDirty(); }}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
