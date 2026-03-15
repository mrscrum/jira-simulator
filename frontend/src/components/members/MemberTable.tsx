import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDeleteMember, useMembers, useUpdateMember } from "@/hooks/useMembers";
import { getRoleColor } from "@/lib/roles";
import type { Member, MemberUpdate } from "@/lib/types";
import { AddMemberModal } from "./AddMemberModal";
import { EditMemberModal } from "./EditMemberModal";

interface MemberTableProps {
  teamId: number;
}

function AvatarInitials({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium">
      {initials}
    </div>
  );
}

export function MemberTable({ teamId }: MemberTableProps) {
  const { data: members = [] } = useMembers(teamId);
  const deleteMember = useDeleteMember(teamId);
  const updateMember = useUpdateMember(teamId);
  const [addOpen, setAddOpen] = useState(false);
  const [editMember, setEditMember] = useState<Member | null>(null);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Team Members</h2>
        <Button onClick={() => setAddOpen(true)} size="sm" data-testid="add-member-btn">
          + Add Member
        </Button>
      </div>

      {members.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-lg border border-dashed text-muted-foreground">
          No members yet
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12" />
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Capacity (h/day)</TableHead>
              <TableHead>Max WIP</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((m) => {
              const roleColor = getRoleColor(m.role);
              return (
                <TableRow key={m.id} data-testid={`member-row-${m.id}`}>
                  <TableCell>
                    <AvatarInitials name={m.name} />
                  </TableCell>
                  <TableCell className="font-medium">{m.name}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={`${roleColor.bg} ${roleColor.text} border ${roleColor.border}`}
                      data-testid={`role-badge-${m.id}`}
                    >
                      {m.role}
                    </Badge>
                  </TableCell>
                  <TableCell>{m.daily_capacity_hours}</TableCell>
                  <TableCell>{m.max_concurrent_wip}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditMember(m)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteMember.mutate(m.id)}
                        data-testid={`delete-member-${m.id}`}
                      >
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <AddMemberModal
        teamId={teamId}
        open={addOpen}
        onClose={() => setAddOpen(false)}
      />

      {editMember && (
        <EditMemberModal
          open={true}
          member={editMember}
          onClose={() => setEditMember(null)}
          onSubmit={(data: MemberUpdate) => {
            updateMember.mutate(
              { memberId: editMember.id, data },
              { onSuccess: () => setEditMember(null) },
            );
          }}
        />
      )}
    </div>
  );
}
