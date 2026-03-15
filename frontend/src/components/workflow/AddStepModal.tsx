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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusPicker } from "@/components/shared/StatusPicker";
import { ROLES } from "@/lib/roles";
import type { WorkflowStepInput } from "@/lib/types";

interface AddStepModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: WorkflowStepInput) => void;
  projectKey: string;
  nextOrder: number;
}

export function AddStepModal({
  open,
  onClose,
  onSubmit,
  projectKey,
  nextOrder,
}: AddStepModalProps) {
  const [jiraStatus, setJiraStatus] = useState("");
  const [roleRequired, setRoleRequired] = useState<string>("Dev");
  const [maxWaitHours, setMaxWaitHours] = useState("24");
  const [wipContribution, setWipContribution] = useState("1");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!jiraStatus.trim()) return;
    onSubmit({
      jira_status: jiraStatus.trim(),
      role_required: roleRequired,
      order: nextOrder,
      max_wait_hours: parseFloat(maxWaitHours),
      wip_contribution: parseFloat(wipContribution),
    });
    setJiraStatus("");
    setRoleRequired("Dev");
    setMaxWaitHours("24");
    setWipContribution("1");
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Step</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Jira Status</Label>
            <StatusPicker
              projectKey={projectKey}
              value={jiraStatus}
              onChange={setJiraStatus}
            />
          </div>
          <div className="space-y-2">
            <Label>Role Responsible</Label>
            <Select value={roleRequired} onValueChange={(v) => v && setRoleRequired(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="max-wait">Max Wait Hours</Label>
              <Input
                id="max-wait"
                type="number"
                min="0"
                value={maxWaitHours}
                onChange={(e) => setMaxWaitHours(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wip-contrib">WIP Contribution</Label>
              <Input
                id="wip-contrib"
                type="number"
                min="0"
                step="0.5"
                value={wipContribution}
                onChange={(e) => setWipContribution(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" data-testid="create-step-btn">
              Add Step
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
