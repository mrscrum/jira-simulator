import { useMemo, useRef, useState } from "react";
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

// Color palette for statuses
const STATUS_COLORS = [
  "#60a5fa", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#94a3b8", "#4ade80",
];

/** Identifies a single bar segment for drag mapping. */
interface SegmentInfo {
  statusIdx: number;
  yIdx: number;
  status: string;
  yLabel: string;
  /** The source config for this segment. */
  config: PreviewConfigItem;
  /** Cumulative x start of this segment (data space). */
  xStart: number;
  /** Width of this segment (data space). */
  width: number;
}

interface DragState {
  segment: SegmentInfo;
  currentX: number; // pixel
}

export function StatusDistributionChart({ configs, onValueChange }: StatusDistributionChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedSize, setSelectedSize] = useState<number | null>(null);
  const drag = usePlotlyDrag();
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);

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

  if (configs.length === 0) return null;

  // Filter configs based on view mode
  let filtered = configs;
  if (viewMode === "by_type" && selectedType) {
    filtered = configs.filter((c) => c.issue_type === selectedType);
  } else if (viewMode === "by_size" && selectedSize !== null) {
    filtered = configs.filter((c) => c.story_points === selectedSize);
  }

  // Build y-axis labels
  const makeLabel = (c: PreviewConfigItem) => {
    if (viewMode === "by_type" && selectedType)
      return c.story_points === 0 ? "Default" : c.story_points + " SP";
    if (viewMode === "by_size" && selectedSize !== null) return c.issue_type;
    return `${c.issue_type} / ${c.story_points === 0 ? "Default" : c.story_points + " SP"}`;
  };

  const yLabels = [...new Set(filtered.map(makeLabel))];

  // Build per-segment lookup: for each (statusIdx, yIdx), what config(s) match?
  const segmentLookup = new Map<string, PreviewConfigItem[]>();
  for (const c of filtered) {
    const label = makeLabel(c);
    for (let si = 0; si < statuses.length; si++) {
      if (c.jira_status === statuses[si]) {
        const key = `${si}:${yLabels.indexOf(label)}`;
        if (!segmentLookup.has(key)) segmentLookup.set(key, []);
        segmentLookup.get(key)!.push(c);
      }
    }
  }

  // Build traces (same logic as before)
  const traces = statuses.map((status, i) => {
    const values = yLabels.map((label) => {
      const matching = filtered.filter((c) => {
        return makeLabel(c) === label && c.jira_status === status;
      });
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
  });

  // Build segment info for drag handles
  const segments: SegmentInfo[] = [];
  for (let yIdx = 0; yIdx < yLabels.length; yIdx++) {
    let cumX = 0;
    for (let si = 0; si < statuses.length; si++) {
      const width = (traces[si].x as number[])[yIdx] ?? 0;
      const key = `${si}:${yIdx}`;
      const matchingConfigs = segmentLookup.get(key);
      if (matchingConfigs && matchingConfigs.length > 0 && width > 0) {
        segments.push({
          statusIdx: si,
          yIdx,
          status: statuses[si],
          yLabel: yLabels[yIdx],
          config: matchingConfigs[0], // use first match for single-config edits
          xStart: cumX,
          width,
        });
      }
      cumX += width;
    }
  }

  // --- Drag handlers ---
  const handlePointerDown = (e: React.PointerEvent, seg: SegmentInfo) => {
    if (!onValueChange) return;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setDragState({
      segment: seg,
      currentX: e.clientX - rect.left,
    });
    e.preventDefault();
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!dragState) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setDragState((prev) => prev ? { ...prev, currentX: e.clientX - rect.left } : null);
  };

  const handlePointerUp = () => {
    if (!dragState || !onValueChange) return;
    const seg = dragState.segment;
    const newRightX = drag.xPixelToData(dragState.currentX);
    const newWidth = Math.max(0.1, Math.round((newRightX - seg.xStart) * 10) / 10);
    onValueChange(
      seg.config.workflow_step_id,
      seg.config.issue_type,
      seg.config.story_points,
      newWidth,
    );
    setDragState(null);
  };

  // Compute drag handle pixel positions
  const handles = useMemo(() => {
    if (!drag.bounds || !onValueChange) return [];
    const cats = drag.yCategories;
    if (!cats) return [];

    return segments.map((seg) => {
      const rightEdgeX = drag.xDataToPixel(seg.xStart + seg.width);
      const catIdx = cats.indexOf(seg.yLabel);
      if (catIdx === -1) return null;
      const centerY = drag.yDataToPixel(catIdx);
      // Bar height: approximate from plot height / number of categories
      const barHalfHeight = drag.bounds!.height / yLabels.length / 2 * 0.7;
      return {
        key: `${seg.statusIdx}-${seg.yIdx}`,
        x: rightEdgeX,
        yTop: centerY - barHalfHeight,
        yBottom: centerY + barHalfHeight,
        segment: seg,
      };
    }).filter(Boolean) as {
      key: string;
      x: number;
      yTop: number;
      yBottom: number;
      segment: SegmentInfo;
    }[];
  }, [drag.bounds, drag.yCategories, drag.xDataToPixel, drag.yDataToPixel, segments, yLabels.length, onValueChange]);

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

      {/* Selector for type or size */}
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
        onPointerMove={dragState ? handlePointerMove : undefined}
        onPointerUp={dragState ? handlePointerUp : undefined}
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
          onInitialized={drag.handlePlotUpdate}
          onUpdate={drag.handlePlotUpdate}
        />
        {/* SVG overlay with drag handles */}
        {drag.bounds && onValueChange && (
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
                dragState.segment.statusIdx === h.segment.statusIdx &&
                dragState.segment.yIdx === h.segment.yIdx;
              const x = isDragging ? dragState!.currentX : h.x;
              const color = STATUS_COLORS[h.segment.statusIdx % STATUS_COLORS.length];
              return (
                <g key={h.key}>
                  <rect
                    x={x - 3}
                    y={h.yTop}
                    width={6}
                    height={h.yBottom - h.yTop}
                    fill={isDragging ? "rgba(0,0,0,0.5)" : "rgba(0,0,0,0.2)"}
                    stroke={color}
                    strokeWidth={1}
                    rx={2}
                    cursor="ew-resize"
                    style={{ pointerEvents: "auto" }}
                    onPointerDown={(e) => handlePointerDown(e, h.segment)}
                  />
                  {/* Small grip dots */}
                  <circle
                    cx={x}
                    cy={(h.yTop + h.yBottom) / 2}
                    r={2}
                    fill="white"
                    style={{ pointerEvents: "none" }}
                  />
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
