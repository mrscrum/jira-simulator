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
import { useCreateMember } from "@/hooks/useMembers";
import { ROLES } from "@/lib/roles";

interface AddMemberModalProps {
  teamId: number;
  open: boolean;
  onClose: () => void;
}

export function AddMemberModal({ teamId, open, onClose }: AddMemberModalProps) {
  const createMember = useCreateMember(teamId);
  const [name, setName] = useState("");
  const [role, setRole] = useState<string>("Dev");
  const [capacity, setCapacity] = useState("7");
  const [maxWip, setMaxWip] = useState("3");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    createMember.mutate(
      {
        name: name.trim(),
        role,
        daily_capacity_hours: parseFloat(capacity),
        max_concurrent_wip: parseInt(maxWip, 10),
      },
      {
        onSuccess: () => {
          setName("");
          setRole("Dev");
          setCapacity("7");
          setMaxWip("3");
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Member</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="member-name">Name</Label>
            <Input
              id="member-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alice"
              required
              data-testid="member-name-input"
            />
          </div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Select value={role} onValueChange={(v) => v && setRole(v)}>
              <SelectTrigger data-testid="member-role-select">
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
              <Label htmlFor="member-capacity">Daily Capacity (hours)</Label>
              <Input
                id="member-capacity"
                type="number"
                min="0"
                step="0.5"
                value={capacity}
                onChange={(e) => setCapacity(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="member-wip">Max Concurrent WIP</Label>
              <Input
                id="member-wip"
                type="number"
                min="1"
                value={maxWip}
                onChange={(e) => setMaxWip(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={createMember.isPending}
              data-testid="create-member-btn"
            >
              {createMember.isPending ? "Adding..." : "Add Member"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
