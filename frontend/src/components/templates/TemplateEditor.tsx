import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTemplate, useUpdateTemplate } from "@/hooks/useTemplates";
import { CycleTimeBoxPlot } from "./CycleTimeBoxPlot";
import type { TimingTemplateEntryInput } from "@/lib/types";

const COMMON_TYPES = ["Story", "Bug", "Task"];
const COMMON_SIZES = [1, 2, 3, 5, 8, 13];

interface TemplateEditorProps {
  templateId: number;
}

export function TemplateEditor({ templateId }: TemplateEditorProps) {
  const { data: template } = useTemplate(templateId);
  const updateTemplate = useUpdateTemplate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [spreadFactor, setSpreadFactor] = useState("0.33");
  const [entries, setEntries] = useState<TimingTemplateEntryInput[]>([]);
  const [dirty, setDirty] = useState(false);
  const [newType, setNewType] = useState("");

  useEffect(() => {
    if (template) {
      setName(template.name);
      setDescription(template.description ?? "");
      setSpreadFactor(String(template.spread_factor));
      setEntries(
        template.entries.map((e) => ({
          issue_type: e.issue_type,
          story_points: e.story_points,
          ct_min: e.ct_min,
          ct_q1: e.ct_q1,
          ct_median: e.ct_median,
          ct_q3: e.ct_q3,
          ct_max: e.ct_max,
        })),
      );
      setDirty(false);
    }
  }, [template]);

  const handleSave = () => {
    updateTemplate.mutate({
      id: templateId,
      data: {
        name,
        description: description || null,
        spread_factor: parseFloat(spreadFactor) || 0.33,
        entries,
      },
    });
    setDirty(false);
  };

  const issueTypes = [...new Set(entries.map((e) => e.issue_type))].sort();
  const sizesForType = (type: string) =>
    [...new Set(entries.filter((e) => e.issue_type === type).map((e) => e.story_points))].sort((a, b) => a - b);

  const getEntry = (type: string, sp: number) =>
    entries.find((e) => e.issue_type === type && e.story_points === sp);

  const updateEntry = useCallback(
    (type: string, sp: number, field: keyof TimingTemplateEntryInput, value: string) => {
      const num = parseFloat(value) || 0;
      setEntries((prev) => {
        const idx = prev.findIndex((e) => e.issue_type === type && e.story_points === sp);
        if (idx === -1) return prev;
        const next = [...prev];
        next[idx] = { ...next[idx], [field]: num };
        return next;
      });
      setDirty(true);
    },
    [],
  );

  const handleBoxPlotChange = useCallback(
    (issueType: string, sp: number, field: keyof TimingTemplateEntryInput, value: number) => {
      updateEntry(issueType, sp, field, String(value));
    },
    [updateEntry],
  );

  const addEntry = (type: string, sp: number) => {
    if (entries.some((e) => e.issue_type === type && e.story_points === sp)) return;
    setEntries((prev) => [
      ...prev,
      { issue_type: type, story_points: sp, ct_min: 1, ct_q1: 2, ct_median: 3, ct_q3: 4, ct_max: 5 },
    ]);
    setDirty(true);
  };

  const removeEntry = (type: string, sp: number) => {
    setEntries((prev) => prev.filter((e) => !(e.issue_type === type && e.story_points === sp)));
    setDirty(true);
  };

  const removeType = (type: string) => {
    setEntries((prev) => prev.filter((e) => e.issue_type !== type));
    setDirty(true);
  };

  const addType = (typeName: string) => {
    if (!typeName.trim()) return;
    addEntry(typeName.trim(), 0);
    setNewType("");
  };

  const addQuickStart = () => {
    const toAdd: TimingTemplateEntryInput[] = [];
    for (const type of COMMON_TYPES) {
      for (const sp of COMMON_SIZES) {
        if (!entries.some((e) => e.issue_type === type && e.story_points === sp)) {
          toAdd.push({ issue_type: type, story_points: sp, ct_min: 1, ct_q1: 2, ct_median: 3, ct_q3: 4, ct_max: 5 });
        }
      }
    }
    setEntries((prev) => [...prev, ...toAdd]);
    setDirty(true);
  };

  if (!template) return null;

  return (
    <div className="space-y-6">
      {/* Header with save */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Edit Template</h2>
        <Button onClick={handleSave} size="sm" disabled={!dirty} className="relative">
          Save
          {dirty && <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-orange-500" />}
        </Button>
      </div>

      {/* Template metadata */}
      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-1">
          <Label className="text-xs">Name</Label>
          <Input
            value={name}
            onChange={(e) => { setName(e.target.value); setDirty(true); }}
            className="h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Description</Label>
          <Input
            value={description}
            onChange={(e) => { setDescription(e.target.value); setDirty(true); }}
            className="h-8 text-sm"
            placeholder="Optional..."
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Spread Factor</Label>
          <Input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={spreadFactor}
            onChange={(e) => { setSpreadFactor(e.target.value); setDirty(true); }}
            className="h-8 text-sm"
          />
        </div>
      </div>

      {/* Entries grid grouped by issue type */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold">Cycle Time Entries (hours)</h3>

        {issueTypes.length === 0 && (
          <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
            No entries yet.
            <Button variant="link" size="sm" onClick={addQuickStart}>Quick Start (Story, Bug, Task)</Button>
          </div>
        )}

        {issueTypes.map((type) => {
          const sizes = sizesForType(type);
          return (
            <div key={type} className="rounded-lg border bg-card">
              <div className="flex items-center gap-2 border-b px-3 py-2">
                <span className="font-semibold text-sm">{type}</span>
                <span className="text-xs text-muted-foreground">({sizes.length} sizes)</span>
                <div className="ml-auto flex items-center gap-1">
                  {COMMON_SIZES.filter((s) => !sizes.includes(s)).length > 0 && (
                    <div className="flex gap-1">
                      {COMMON_SIZES.filter((s) => !sizes.includes(s)).map((s) => (
                        <button
                          key={s}
                          className="rounded border px-1.5 py-0.5 text-[10px] hover:bg-accent"
                          onClick={() => addEntry(type, s)}
                        >
                          +{s}SP
                        </button>
                      ))}
                    </div>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs text-destructive hover:text-destructive"
                    onClick={() => removeType(type)}
                  >
                    Remove Type
                  </Button>
                </div>
              </div>

              {/* Column headers */}
              <div className="grid grid-cols-[60px_repeat(5,1fr)_24px] gap-1 px-3 py-1 text-[10px] text-muted-foreground">
                <span>Size</span>
                <span className="text-center">Min</span>
                <span className="text-center">Q1 (p25)</span>
                <span className="text-center">Median (p50)</span>
                <span className="text-center">Q3 (p75)</span>
                <span className="text-center">Max</span>
                <span />
              </div>

              {/* Entry rows */}
              {sizes.map((sp) => {
                const entry = getEntry(type, sp);
                if (!entry) return null;
                return (
                  <div
                    key={sp}
                    className="grid grid-cols-[60px_repeat(5,1fr)_24px] items-center gap-1 px-3 py-0.5"
                  >
                    <span className="text-xs font-medium">{sp === 0 ? "Default" : `${sp} SP`}</span>
                    {(["ct_min", "ct_q1", "ct_median", "ct_q3", "ct_max"] as const).map((field) => (
                      <Input
                        key={field}
                        type="number"
                        min="0"
                        step="0.5"
                        className="h-6 px-1 text-center text-xs"
                        value={entry[field] || ""}
                        onChange={(e) => updateEntry(type, sp, field, e.target.value)}
                        placeholder="0"
                      />
                    ))}
                    <button
                      className="text-xs text-muted-foreground hover:text-destructive"
                      onClick={() => removeEntry(type, sp)}
                    >
                      ×
                    </button>
                  </div>
                );
              })}
            </div>
          );
        })}

        {/* Add issue type */}
        <div className="flex items-center gap-2">
          <Input
            className="h-8 w-40 text-sm"
            placeholder="New issue type..."
            value={newType}
            onChange={(e) => setNewType(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") addType(newType); }}
          />
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            disabled={!newType.trim()}
            onClick={() => addType(newType)}
          >
            + Add Type
          </Button>
          {issueTypes.length > 0 && (
            <Button variant="outline" size="sm" className="h-8" onClick={addQuickStart}>
              Quick Start
            </Button>
          )}
        </div>
      </div>

      {/* Cycle Time Box Plot — interactive */}
      <CycleTimeBoxPlot entries={entries} onEntryChange={handleBoxPlotChange} />
    </div>
  );
}
