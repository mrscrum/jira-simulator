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
import { useTeams } from "@/hooks/useTeams";
import * as api from "@/lib/api";
import { DYSFUNCTIONS } from "@/lib/dysfunctions";

interface InjectModalProps {
  open: boolean;
  onClose: () => void;
}

export function InjectModal({ open, onClose }: InjectModalProps) {
  const { data: teams = [] } = useTeams();
  const [teamId, setTeamId] = useState<string>("");
  const [dysfunctionType, setDysfunctionType] = useState<string>("");
  const [targetIssue, setTargetIssue] = useState("");
  const [firing, setFiring] = useState(false);

  const handleFire = async () => {
    if (!teamId || !dysfunctionType) return;
    setFiring(true);
    await api.injectDysfunction({
      team_id: parseInt(teamId),
      dysfunction_type: dysfunctionType,
    });
    setFiring(false);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Inject Dysfunction</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Team</Label>
            <Select value={teamId} onValueChange={(v) => v && setTeamId(v)}>
              <SelectTrigger data-testid="inject-team-select">
                <SelectValue placeholder="Select team..." />
              </SelectTrigger>
              <SelectContent>
                {teams.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Dysfunction Type</Label>
            <Select
              value={dysfunctionType}
              onValueChange={(v) => v && setDysfunctionType(v)}
            >
              <SelectTrigger data-testid="inject-type-select">
                <SelectValue placeholder="Select type..." />
              </SelectTrigger>
              <SelectContent>
                {DYSFUNCTIONS.map((d) => (
                  <SelectItem key={d.type} value={d.type}>
                    {d.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="target-issue">Target Issue Key (optional)</Label>
            <Input
              id="target-issue"
              value={targetIssue}
              onChange={(e) => setTargetIssue(e.target.value)}
              placeholder="e.g. ALPHA-42"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleFire}
            disabled={firing || !teamId || !dysfunctionType}
            data-testid="inject-fire-btn"
          >
            {firing ? "Firing..." : "Fire"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
