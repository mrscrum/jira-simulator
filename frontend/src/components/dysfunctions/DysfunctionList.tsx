import { useState } from "react";
import { useDysfunctions, useUpdateDysfunction } from "@/hooks/useDysfunctions";
import { DYSFUNCTIONS } from "@/lib/dysfunctions";
import type { DysfunctionMeta } from "@/lib/dysfunctions";
import type { DysfunctionConfigUpdate } from "@/lib/types";
import { DysfunctionCard } from "./DysfunctionCard";
import { DysfunctionModal } from "./DysfunctionModal";

interface DysfunctionListProps {
  teamId: number;
}

export function DysfunctionList({ teamId }: DysfunctionListProps) {
  const { data: config } = useDysfunctions(teamId);
  const updateDysfunction = useUpdateDysfunction(teamId);
  const [editMeta, setEditMeta] = useState<DysfunctionMeta | null>(null);

  if (!config) {
    return <div className="text-muted-foreground">Loading dysfunctions...</div>;
  }

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Dysfunctions</h2>
      <div className="space-y-3">
        {DYSFUNCTIONS.map((meta) => (
          <DysfunctionCard
            key={meta.type}
            meta={meta}
            config={config}
            onProbabilityChange={(value) => {
              updateDysfunction.mutate({
                type: meta.type,
                data: { [meta.probabilityField]: value } as DysfunctionConfigUpdate,
              });
            }}
            onToggle={(enabled) => {
              updateDysfunction.mutate({
                type: meta.type,
                data: {
                  [meta.probabilityField]: enabled ? 0.15 : 0,
                } as DysfunctionConfigUpdate,
              });
            }}
            onEdit={() => setEditMeta(meta)}
          />
        ))}
      </div>

      {editMeta && (
        <DysfunctionModal
          open={true}
          onClose={() => setEditMeta(null)}
          meta={editMeta}
          config={config}
          onSave={(data) => {
            updateDysfunction.mutate({ type: editMeta.type, data });
          }}
        />
      )}
    </div>
  );
}
