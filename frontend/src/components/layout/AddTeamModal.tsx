import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { TeamCreate } from "@/lib/types";

interface AddTeamModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: TeamCreate) => void;
  loading?: boolean;
}

export function AddTeamModal({
  open,
  onClose,
  onSubmit,
  loading,
}: AddTeamModalProps) {
  const [name, setName] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [sprintLength, setSprintLength] = useState("10");
  const [capMin, setCapMin] = useState("20");
  const [capMax, setCapMax] = useState("40");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !projectKey.trim()) return;
    onSubmit({
      name: name.trim(),
      jira_project_key: projectKey.trim().toUpperCase(),
      sprint_length_days: parseInt(sprintLength, 10) || 10,
      sprint_capacity_min: parseInt(capMin, 10) || 20,
      sprint_capacity_max: parseInt(capMax, 10) || 40,
    });
    setName("");
    setProjectKey("");
    setSprintLength("10");
    setCapMin("20");
    setCapMax("40");
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Team</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="team-name">Team Name</Label>
              <Input
                id="team-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Platform"
                required
                data-testid="team-name-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-key">Jira Project Key</Label>
              <Input
                id="project-key"
                value={projectKey}
                onChange={(e) => setProjectKey(e.target.value.toUpperCase())}
                placeholder="e.g. PLAT"
                required
                data-testid="project-key-input"
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="sprint-len">Sprint Length (days)</Label>
              <Input
                id="sprint-len"
                type="number"
                min="1"
                max="30"
                value={sprintLength}
                onChange={(e) => setSprintLength(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cap-min">Capacity Min (SP)</Label>
              <Input
                id="cap-min"
                type="number"
                min="1"
                value={capMin}
                onChange={(e) => setCapMin(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cap-max">Capacity Max (SP)</Label>
              <Input
                id="cap-max"
                type="number"
                min="1"
                value={capMax}
                onChange={(e) => setCapMax(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading} data-testid="create-team-btn">
              {loading ? "Creating..." : "Create Team"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
