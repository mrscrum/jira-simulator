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
import { ROLES } from "@/lib/roles";
import type { Member, MemberUpdate } from "@/lib/types";

interface EditMemberModalProps {
  open: boolean;
  member: Member;
  onClose: () => void;
  onSubmit: (data: MemberUpdate) => void;
}

export function EditMemberModal({
  open,
  member,
  onClose,
  onSubmit,
}: EditMemberModalProps) {
  const [name, setName] = useState(member.name);
  const [role, setRole] = useState(member.role);
  const [capacity, setCapacity] = useState(String(member.daily_capacity_hours));
  const [maxWip, setMaxWip] = useState(String(member.max_concurrent_wip));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      name: name.trim(),
      role,
      daily_capacity_hours: parseFloat(capacity),
      max_concurrent_wip: parseInt(maxWip, 10),
    });
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Member</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-member-name">Name</Label>
            <Input
              id="edit-member-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label>Role</Label>
            <Select value={role} onValueChange={(v) => v && setRole(v)}>
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
              <Label htmlFor="edit-capacity">Daily Capacity (hours)</Label>
              <Input
                id="edit-capacity"
                type="number"
                min="0"
                step="0.5"
                value={capacity}
                onChange={(e) => setCapacity(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-wip">Max Concurrent WIP</Label>
              <Input
                id="edit-wip"
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
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
