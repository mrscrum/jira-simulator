import { useCallback, useMemo, useRef } from "react";
import { Button } from "@/components/ui/button";
import Plot from "./PlotlyChart";
import { usePlotlyDrag } from "./usePlotlyDrag";
import type { TimingTemplateEntryInput } from "@/lib/types";
import { useState } from "react";

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

interface DragInfo {
  issueType: string;
  sp: number;
  field: BoxField;
  fieldIdx: number;
  circle: SVGCircleElement;
}

export function CycleTimeBoxPlot({ entries, onEntryChange }: CycleTimeBoxPlotProps) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const drag = usePlotlyDrag();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<DragInfo | null>(null);

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

  const sorted = useMemo(
    () => [...filtered].sort((a, b) => a.story_points - b.story_points),
    [filtered],
  );

  // Keep sorted in a ref so positionHandles can read current data without being re-created
  const sortedRef = useRef(sorted);
  sortedRef.current = sorted;

  const data = useMemo(
    () =>
      sorted.map((e) => {
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
      }),
    [sorted],
  );

  // Position SVG handles — called directly from Plotly callback, never from useEffect
  const positionHandles = useCallback(() => {
    const svg = svgRef.current;
    if (!svg || !onEntryChange) return;

    const bounds = drag.getBounds();
    const cats = drag.getXCategories();
    if (!bounds || !cats) return;

    // Don't clear if we're mid-drag (the user is holding a handle)
    if (dragRef.current) return;

    // Clear old handles
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const currentSorted = sortedRef.current;

    for (const entry of currentSorted) {
      const label = entry.story_points === 0 ? "Default" : `${entry.story_points} SP`;
      const catIdx = cats.indexOf(label);
      if (catIdx === -1) continue;
      const cx = drag.xDataToPixel(catIdx);

      for (let fi = 0; fi < FIELDS.length; fi++) {
        const field = FIELDS[fi];
        const val = entry[field];
        const cy = drag.yDataToPixel(val);

        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", String(cx));
        circle.setAttribute("cy", String(cy));
        circle.setAttribute("r", "6");
        circle.setAttribute("fill", "rgba(59,130,246,0.4)");
        circle.setAttribute("stroke", "rgb(59,130,246)");
        circle.setAttribute("stroke-width", "1.5");
        circle.setAttribute("cursor", "ns-resize");
        circle.style.pointerEvents = "auto";
        circle.dataset.issueType = entry.issue_type;
        circle.dataset.sp = String(entry.story_points);
        circle.dataset.field = field;
        circle.dataset.fieldIdx = String(fi);

        svg.appendChild(circle);
      }
    }
  }, [onEntryChange, drag]);

  // Called by Plotly on both onInitialized and onUpdate
  const handlePlotReady = useCallback(
    (figure: unknown, graphDiv: HTMLElement) => {
      drag.handlePlotUpdate(figure, graphDiv);
      // Position handles directly — no React state change, no re-render loop
      requestAnimationFrame(positionHandles);
    },
    [drag, positionHandles],
  );

  // Pointer event handlers on the container
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!onEntryChange) return;
      const target = e.target as SVGCircleElement;
      if (target.tagName !== "circle" || !target.dataset.field) return;

      target.setPointerCapture(e.pointerId);
      target.setAttribute("r", "8");
      target.setAttribute("fill", "rgba(59,130,246,0.8)");

      dragRef.current = {
        issueType: target.dataset.issueType!,
        sp: Number(target.dataset.sp),
        field: target.dataset.field as BoxField,
        fieldIdx: Number(target.dataset.fieldIdx),
        circle: target,
      };
      e.preventDefault();
    },
    [onEntryChange],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const py = e.clientY - rect.top;
      d.circle.setAttribute("cy", String(py));
    },
    [],
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent) => {
      const d = dragRef.current;
      if (!d || !onEntryChange) return;
      dragRef.current = null;

      d.circle.setAttribute("r", "6");
      d.circle.setAttribute("fill", "rgba(59,130,246,0.4)");

      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const py = e.clientY - rect.top;
      const dataVal = Math.max(0, Math.round(drag.yPixelToData(py) * 10) / 10);

      const entry = entries.find(
        (en) => en.issue_type === d.issueType && en.story_points === d.sp,
      );
      if (entry) {
        const vals = FIELDS.map((f) => entry[f]);
        vals[d.fieldIdx] = dataVal;
        // Enforce ordering constraints
        for (let i = d.fieldIdx - 1; i >= 0; i--) {
          if (vals[i] > vals[i + 1]) vals[i] = vals[i + 1];
        }
        for (let i = d.fieldIdx + 1; i < vals.length; i++) {
          if (vals[i] < vals[i - 1]) vals[i] = vals[i - 1];
        }
        for (let i = 0; i < FIELDS.length; i++) {
          if (vals[i] !== entry[FIELDS[i]]) {
            onEntryChange(d.issueType, d.sp, FIELDS[i], vals[i]);
          }
        }
      }
    },
    [onEntryChange, entries, drag],
  );

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
        onPointerDown={onEntryChange ? handlePointerDown : undefined}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
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
          onInitialized={handlePlotReady}
          onUpdate={handlePlotReady}
        />
        {onEntryChange && (
          <svg
            ref={svgRef}
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: "100%",
              height: "100%",
              pointerEvents: "none",
            }}
          />
        )}
      </div>
    </div>
  );
}
