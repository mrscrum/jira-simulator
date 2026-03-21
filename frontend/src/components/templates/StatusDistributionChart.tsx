import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Plot from "./PlotlyChart";
import { Button } from "@/components/ui/button";
import { usePlotlyDrag } from "./usePlotlyDrag";
import type { PreviewConfigItem } from "@/lib/types";

type ViewMode = "all" | "by_type" | "by_size";

interface StatusDistributionChartProps {
  configs: PreviewConfigItem[];
  onValueChange?: (
    workflowStepId: number,
    issueType: string,
    storyPoints: number,
    newP50: number,
  ) => void;
}

const STATUS_COLORS = [
  "#60a5fa", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#94a3b8", "#4ade80",
];

interface SegmentInfo {
  statusIdx: number;
  yIdx: number;
  status: string;
  yLabel: string;
  workflowStepId: number;
  issueType: string;
  storyPoints: number;
  xStart: number;
  width: number;
}

interface DragInfo {
  segment: SegmentInfo;
  handle: SVGRectElement;
}

export function StatusDistributionChart({ configs, onValueChange }: StatusDistributionChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedSize, setSelectedSize] = useState<number | null>(null);
  const drag = usePlotlyDrag();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<DragInfo | null>(null);
  const segmentsRef = useRef<SegmentInfo[]>([]);
  const [plotReady, setPlotReady] = useState(false);

  const issueTypes = useMemo(
    () => [...new Set(configs.map((c) => c.issue_type))].sort(),
    [configs],
  );
  const sizes = useMemo(
    () => [...new Set(configs.map((c) => c.story_points))].sort((a, b) => a - b),
    [configs],
  );
  const statuses = useMemo(() => {
    const seen = new Map<string, string | null>();
    for (const c of configs) {
      if (!seen.has(c.jira_status)) seen.set(c.jira_status, c.status_category);
    }
    const entries = [...seen.entries()];
    const order = { todo: 0, in_progress: 1, done: 2 };
    entries.sort((a, b) => {
      const oa = order[(a[1] as keyof typeof order) ?? "in_progress"] ?? 1;
      const ob = order[(b[1] as keyof typeof order) ?? "in_progress"] ?? 1;
      return oa - ob;
    });
    return entries.map(([name]) => name);
  }, [configs]);

  const filtered = useMemo(() => {
    if (viewMode === "by_type" && selectedType) {
      return configs.filter((c) => c.issue_type === selectedType);
    }
    if (viewMode === "by_size" && selectedSize !== null) {
      return configs.filter((c) => c.story_points === selectedSize);
    }
    return configs;
  }, [configs, viewMode, selectedType, selectedSize]);

  const makeLabel = useCallback(
    (c: PreviewConfigItem) => {
      if (viewMode === "by_type" && selectedType)
        return c.story_points === 0 ? "Default" : c.story_points + " SP";
      if (viewMode === "by_size" && selectedSize !== null) return c.issue_type;
      return `${c.issue_type} / ${c.story_points === 0 ? "Default" : c.story_points + " SP"}`;
    },
    [viewMode, selectedType, selectedSize],
  );

  const yLabels = useMemo(
    () => [...new Set(filtered.map(makeLabel))],
    [filtered, makeLabel],
  );

  // Build segment lookup
  const segmentLookup = useMemo(() => {
    const lookup = new Map<string, PreviewConfigItem[]>();
    for (const c of filtered) {
      const label = makeLabel(c);
      for (let si = 0; si < statuses.length; si++) {
        if (c.jira_status === statuses[si]) {
          const key = `${si}:${yLabels.indexOf(label)}`;
          if (!lookup.has(key)) lookup.set(key, []);
          lookup.get(key)!.push(c);
        }
      }
    }
    return lookup;
  }, [filtered, makeLabel, statuses, yLabels]);

  const traces = useMemo(
    () =>
      statuses.map((status, i) => {
        const values = yLabels.map((label) => {
          const matching = filtered.filter(
            (c) => makeLabel(c) === label && c.jira_status === status,
          );
          if (matching.length === 0) return 0;
          return matching.reduce((sum, c) => sum + (c.full_time_p50 ?? 0), 0) / matching.length;
        });
        return {
          type: "bar" as const,
          name: status,
          y: yLabels,
          x: values,
          orientation: "h" as const,
          marker: { color: STATUS_COLORS[i % STATUS_COLORS.length] },
        };
      }),
    [statuses, yLabels, filtered, makeLabel],
  );

  // Build segments for drag handles
  const segments = useMemo(() => {
    const result: SegmentInfo[] = [];
    for (let yIdx = 0; yIdx < yLabels.length; yIdx++) {
      let cumX = 0;
      for (let si = 0; si < statuses.length; si++) {
        const width = (traces[si].x as number[])[yIdx] ?? 0;
        const key = `${si}:${yIdx}`;
        const matchingConfigs = segmentLookup.get(key);
        if (matchingConfigs && matchingConfigs.length > 0 && width > 0) {
          const cfg = matchingConfigs[0];
          result.push({
            statusIdx: si,
            yIdx,
            status: statuses[si],
            yLabel: yLabels[yIdx],
            workflowStepId: cfg.workflow_step_id,
            issueType: cfg.issue_type,
            storyPoints: cfg.story_points,
            xStart: cumX,
            width,
          });
        }
        cumX += width;
      }
    }
    return result;
  }, [yLabels, statuses, traces, segmentLookup]);

  // Keep segments ref current for pointer handlers
  useEffect(() => {
    segmentsRef.current = segments;
  }, [segments]);

  const handlePlotUpdate = useCallback(
    (figure: unknown, graphDiv: HTMLElement) => {
      drag.handlePlotUpdate(figure, graphDiv);
      setPlotReady(true);
    },
    [drag],
  );

  // Position SVG handles imperatively after plot renders
  useEffect(() => {
    if (!plotReady || !onValueChange) return;
    const svg = svgRef.current;
    if (!svg) return;

    const bounds = drag.getBounds();
    const cats = drag.getYCategories();
    if (!bounds || !cats) return;

    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const barHalfHeight = (bounds.height / yLabels.length / 2) * 0.7;

    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];
      const rightEdgeX = drag.xDataToPixel(seg.xStart + seg.width);
      const catIdx = cats.indexOf(seg.yLabel);
      if (catIdx === -1) continue;
      const centerY = drag.yDataToPixel(catIdx);
      const color = STATUS_COLORS[seg.statusIdx % STATUS_COLORS.length];

      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(rightEdgeX - 3));
      rect.setAttribute("y", String(centerY - barHalfHeight));
      rect.setAttribute("width", "6");
      rect.setAttribute("height", String(barHalfHeight * 2));
      rect.setAttribute("fill", "rgba(0,0,0,0.2)");
      rect.setAttribute("stroke", color);
      rect.setAttribute("stroke-width", "1");
      rect.setAttribute("rx", "2");
      rect.setAttribute("cursor", "ew-resize");
      rect.style.pointerEvents = "auto";
      rect.dataset.segIdx = String(i);

      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", String(rightEdgeX));
      dot.setAttribute("cy", String(centerY));
      dot.setAttribute("r", "2");
      dot.setAttribute("fill", "white");
      dot.style.pointerEvents = "none";

      g.appendChild(rect);
      g.appendChild(dot);
      svg.appendChild(g);
    }
  }, [plotReady, segments, yLabels.length, onValueChange, drag]);

  // Pointer handlers — use refs, no React state during drag
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!onValueChange) return;
      const target = e.target as SVGRectElement;
      if (target.tagName !== "rect" || !target.dataset.segIdx) return;

      const segIdx = Number(target.dataset.segIdx);
      const seg = segmentsRef.current[segIdx];
      if (!seg) return;

      (target as SVGRectElement).setPointerCapture(e.pointerId);
      target.setAttribute("fill", "rgba(0,0,0,0.5)");

      dragRef.current = { segment: seg, handle: target };
      e.preventDefault();
    },
    [onValueChange],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const px = e.clientX - rect.left;
      // Move the handle rect directly in the DOM
      d.handle.setAttribute("x", String(px - 3));
      // Move the grip dot too
      const dot = d.handle.nextElementSibling as SVGCircleElement | null;
      if (dot) dot.setAttribute("cx", String(px));
    },
    [],
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent) => {
      const d = dragRef.current;
      if (!d || !onValueChange) return;
      dragRef.current = null;

      d.handle.setAttribute("fill", "rgba(0,0,0,0.2)");

      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const px = e.clientX - rect.left;
      const newRightX = drag.xPixelToData(px);
      const newWidth = Math.max(0.1, Math.round((newRightX - d.segment.xStart) * 10) / 10);

      onValueChange(
        d.segment.workflowStepId,
        d.segment.issueType,
        d.segment.storyPoints,
        newWidth,
      );
    },
    [onValueChange, drag],
  );

  if (configs.length === 0) return null;

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Expected Time in Status (p50, hours)</h3>
        {onValueChange && (
          <span className="text-[10px] text-muted-foreground">Drag edges to edit</span>
        )}
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant={viewMode === "all" ? "default" : "outline"}
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => setViewMode("all")}
          >
            All
          </Button>
          <Button
            variant={viewMode === "by_type" ? "default" : "outline"}
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => {
              setViewMode("by_type");
              if (!selectedType && issueTypes.length > 0) setSelectedType(issueTypes[0]);
            }}
          >
            By Type
          </Button>
          <Button
            variant={viewMode === "by_size" ? "default" : "outline"}
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => {
              setViewMode("by_size");
              if (selectedSize === null && sizes.length > 0) setSelectedSize(sizes[0]);
            }}
          >
            By Size
          </Button>
        </div>
      </div>

      {viewMode === "by_type" && (
        <div className="mb-2 flex gap-1">
          {issueTypes.map((t) => (
            <Button
              key={t}
              variant={selectedType === t ? "default" : "outline"}
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => setSelectedType(t)}
            >
              {t}
            </Button>
          ))}
        </div>
      )}
      {viewMode === "by_size" && (
        <div className="mb-2 flex gap-1">
          {sizes.map((s) => (
            <Button
              key={s}
              variant={selectedSize === s ? "default" : "outline"}
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => setSelectedSize(s)}
            >
              {s === 0 ? "Default" : `${s} SP`}
            </Button>
          ))}
        </div>
      )}

      <div
        ref={containerRef}
        className="relative"
        onPointerDown={onValueChange ? handlePointerDown : undefined}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <Plot
          data={traces}
          layout={{
            barmode: "stack",
            height: Math.max(200, yLabels.length * 30 + 80),
            margin: { t: 10, b: 40, l: 120, r: 20 },
            xaxis: { title: { text: "Hours" } },
            yaxis: { autorange: "reversed" as const },
            legend: { orientation: "h" as const, y: -0.15 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { size: 11 },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
          onInitialized={handlePlotUpdate}
          onUpdate={handlePlotUpdate}
        />
        {onValueChange && (
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
