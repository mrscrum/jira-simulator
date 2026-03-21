import { useCallback, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import Plot from "./PlotlyChart";
import { usePlotlyDrag } from "./usePlotlyDrag";
import type { TimingTemplateEntryInput } from "@/lib/types";

const FIELDS = ["ct_min", "ct_q1", "ct_median", "ct_q3", "ct_max"] as const;
type BoxField = (typeof FIELDS)[number];

interface CycleTimeBoxPlotProps {
  entries: TimingTemplateEntryInput[];
  onEntryChange?: (
    issueType: string,
    sp: number,
    field: BoxField,
    value: number,
  ) => void;
}

interface DragState {
  issueType: string;
  sp: number;
  field: BoxField;
  fieldIdx: number;
  currentY: number; // pixel
}

export function CycleTimeBoxPlot({ entries, onEntryChange }: CycleTimeBoxPlotProps) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const drag = usePlotlyDrag();
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);

  const validEntries = useMemo(
    () => entries.filter((e) => e.ct_median > 0),
    [entries],
  );

  const issueTypes = useMemo(
    () => [...new Set(validEntries.map((e) => e.issue_type))].sort(),
    [validEntries],
  );

  const activeType = selectedType && issueTypes.includes(selectedType)
    ? selectedType
    : issueTypes[0] ?? null;

  const filtered = activeType
    ? validEntries.filter((e) => e.issue_type === activeType)
    : validEntries;

  const sorted = [...filtered].sort((a, b) => a.story_points - b.story_points);

  const data = sorted.map((e) => {
    const label = e.story_points === 0 ? "Default" : `${e.story_points} SP`;
    return {
      type: "box" as const,
      name: label,
      x: [label],
      lowerfence: [e.ct_min],
      q1: [e.ct_q1],
      median: [e.ct_median],
      q3: [e.ct_q3],
      upperfence: [e.ct_max],
      boxpoints: false as const,
    };
  });

  // --- Drag logic ---

  const handlePointerDown = useCallback(
    (e: React.PointerEvent, issueType: string, sp: number, field: BoxField, fieldIdx: number) => {
      if (!onEntryChange) return;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setDragState({
        issueType,
        sp,
        field,
        fieldIdx,
        currentY: e.clientY - rect.top,
      });
      e.preventDefault();
    },
    [onEntryChange],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragState) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setDragState((prev) => prev ? { ...prev, currentY: e.clientY - rect.top } : null);
    },
    [dragState],
  );

  const handlePointerUp = useCallback(
    (_e: React.PointerEvent) => {
      if (!dragState || !onEntryChange) return;
      const dataVal = Math.max(0, Math.round(drag.yPixelToData(dragState.currentY) * 10) / 10);

      // Enforce constraints: find current entry values
      const entry = entries.find(
        (en) => en.issue_type === dragState.issueType && en.story_points === dragState.sp,
      );
      if (entry) {
        const vals = FIELDS.map((f) => entry[f]);
        vals[dragState.fieldIdx] = dataVal;
        // Clamp to maintain ordering
        for (let i = dragState.fieldIdx - 1; i >= 0; i--) {
          if (vals[i] > vals[i + 1]) vals[i] = vals[i + 1];
        }
        for (let i = dragState.fieldIdx + 1; i < vals.length; i++) {
          if (vals[i] < vals[i - 1]) vals[i] = vals[i - 1];
        }
        // Apply all changed values
        for (let i = 0; i < FIELDS.length; i++) {
          if (vals[i] !== entry[FIELDS[i]]) {
            onEntryChange(dragState.issueType, dragState.sp, FIELDS[i], vals[i]);
          }
        }
      }
      setDragState(null);
    },
    [dragState, onEntryChange, entries, drag],
  );

  // --- Compute handle positions ---
  const handles = useMemo(() => {
    if (!drag.bounds || !onEntryChange) return [];
    const result: {
      key: string;
      cx: number;
      cy: number;
      issueType: string;
      sp: number;
      field: BoxField;
      fieldIdx: number;
    }[] = [];

    const cats = drag.xCategories;
    if (!cats) return result;

    for (const entry of sorted) {
      const label = entry.story_points === 0 ? "Default" : `${entry.story_points} SP`;
      const catIdx = cats.indexOf(label);
      if (catIdx === -1) continue;
      const cx = drag.xDataToPixel(catIdx);

      for (let fi = 0; fi < FIELDS.length; fi++) {
        const field = FIELDS[fi];
        const val = entry[field];
        const cy = drag.yDataToPixel(val);
        result.push({
          key: `${entry.issue_type}-${entry.story_points}-${field}`,
          cx,
          cy,
          issueType: entry.issue_type,
          sp: entry.story_points,
          field,
          fieldIdx: fi,
        });
      }
    }
    return result;
  }, [drag.bounds, drag.xCategories, drag.xDataToPixel, drag.yDataToPixel, sorted, onEntryChange]);

  if (validEntries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
        Enter cycle time values to see the distribution chart.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Cycle Time Distribution</h3>
        {onEntryChange && (
          <span className="text-[10px] text-muted-foreground">Drag handles to edit</span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {issueTypes.map((type) => (
            <Button
              key={type}
              variant={activeType === type ? "default" : "outline"}
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => setSelectedType(type)}
            >
              {type}
            </Button>
          ))}
        </div>
      </div>
      <div
        ref={containerRef}
        className="relative"
        onPointerMove={dragState ? handlePointerMove : undefined}
        onPointerUp={dragState ? handlePointerUp : undefined}
      >
        <Plot
          data={data}
          layout={{
            height: 300,
            margin: { t: 20, b: 60, l: 50, r: 20 },
            yaxis: { title: { text: "Hours" }, zeroline: true },
            xaxis: { type: "category" as const, tickangle: -45 },
            boxmode: "group" as const,
            showlegend: false,
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { size: 11 },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
          onInitialized={drag.handlePlotUpdate}
          onUpdate={drag.handlePlotUpdate}
        />
        {/* SVG overlay with drag handles */}
        {drag.bounds && onEntryChange && (
          <svg
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: "100%",
              height: "100%",
              pointerEvents: "none",
            }}
          >
            {handles.map((h) => {
              const isDragging =
                dragState &&
                dragState.issueType === h.issueType &&
                dragState.sp === h.sp &&
                dragState.field === h.field;
              const cy = isDragging ? dragState!.currentY : h.cy;
              return (
                <circle
                  key={h.key}
                  cx={h.cx}
                  cy={cy}
                  r={isDragging ? 7 : 5}
                  fill={isDragging ? "rgba(59,130,246,0.8)" : "rgba(59,130,246,0.4)"}
                  stroke="rgb(59,130,246)"
                  strokeWidth={1.5}
                  cursor="ns-resize"
                  style={{ pointerEvents: "auto" }}
                  onPointerDown={(e) =>
                    handlePointerDown(e, h.issueType, h.sp, h.field, h.fieldIdx)
                  }
                />
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
