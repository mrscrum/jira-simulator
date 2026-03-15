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

interface AddTeamModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: { name: string; jira_project_key: string }) => void;
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !projectKey.trim()) return;
    onSubmit({ name: name.trim(), jira_project_key: projectKey.trim().toUpperCase() });
    setName("");
    setProjectKey("");
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Team</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
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
