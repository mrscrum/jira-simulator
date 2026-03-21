import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTemplates, useCreateTemplate, useDeleteTemplate } from "@/hooks/useTemplates";
import type { TimingTemplate } from "@/lib/types";

interface TemplateListProps {
  activeTemplateId: number | null;
  onSelect: (id: number) => void;
}

export function TemplateList({ activeTemplateId, onSelect }: TemplateListProps) {
  const { data: templates = [] } = useTemplates();
  const createTemplate = useCreateTemplate();
  const deleteTemplate = useDeleteTemplate();
  const [newName, setNewName] = useState("");

  const handleCreate = () => {
    if (!newName.trim()) return;
    createTemplate.mutate(
      { name: newName.trim(), entries: [] },
      { onSuccess: (t) => { onSelect(t.id); setNewName(""); } },
    );
  };

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Timing Templates</h2>

      {templates.length === 0 && (
        <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
          No templates yet. Create one to get started.
        </div>
      )}

      <div className="space-y-1">
        {templates.map((t: TimingTemplate) => (
          <div
            key={t.id}
            className={`flex items-center justify-between rounded-md px-3 py-2 text-sm cursor-pointer ${
              t.id === activeTemplateId
                ? "bg-accent text-accent-foreground font-medium"
                : "hover:bg-accent/50"
            }`}
            onClick={() => onSelect(t.id)}
          >
            <div>
              <span>{t.name}</span>
              {t.description && (
                <span className="ml-2 text-xs text-muted-foreground">{t.description}</span>
              )}
              <span className="ml-2 text-xs text-muted-foreground">
                ({t.entries.length} entries)
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-destructive hover:text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                deleteTemplate.mutate(t.id);
              }}
            >
              Delete
            </Button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Input
          className="h-8 w-48 text-sm"
          placeholder="New template name..."
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
        />
        <Button
          variant="outline"
          size="sm"
          className="h-8"
          disabled={!newName.trim() || createTemplate.isPending}
          onClick={handleCreate}
        >
          + Create Template
        </Button>
      </div>
    </div>
  );
}
