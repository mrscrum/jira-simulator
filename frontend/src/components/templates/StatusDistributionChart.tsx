import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { PreviewConfigItem } from "@/lib/types";

type ViewMode = "all" | "by_type" | "by_size";

const STATUS_COLORS = [
  "#60a5fa", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#94a3b8", "#4ade80",
];

const MARGIN = { top: 10, right: 20, bottom: 40, left: 120 };
const BAR_HEIGHT = 24;
const BAR_GAP = 6;
const HANDLE_WIDTH = 8;

interface StatusDistributionChartProps {
  configs: PreviewConfigItem[];
  onValueChange?: (
    workflowStepId: number,
    issueType: string,
    storyPoints: number,
    newP50: number,
  ) => void;
}

interface SegmentInfo {
  statusIdx: number;
  rowIdx: number;
  status: string;
  workflowStepId: number;
  issueType: string;
  storyPoints: number;
  xStart: number;
  width: number;
}

interface DragState {
  segIdx: number;
  currentWidth: number;
}

/* ---------- axis helpers ---------- */

function niceStep(range: number, targetTicks: number): number {
  const raw = range / targetTicks;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const nice = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  return nice * mag;
}

function makeTicks(max: number, target = 6): number[] {
  if (max <= 0) return [0];
  const step = niceStep(max, target);
  const ticks: number[] = [];
  for (let v = 0; v <= max + step * 0.01; v += step) {
    ticks.push(Math.round(v * 1e6) / 1e6);
  }
  return ticks;
}

export function StatusDistributionChart({
  configs,
  onValueChange,
}: StatusDistributionChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedSize, setSelectedSize] = useState<number | null>(null);
  const [width, setWidth] = useState(800);
  const [drag, setDrag] = useState<DragState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  /* responsive width */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((es) => {
      const w = es[0]?.contentRect.width;
      if (w && w > 0) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* unique values */
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

  /* filter by view */
  const filtered = useMemo(() => {
    if (viewMode === "by_type" && selectedType)
      return configs.filter((c) => c.issue_type === selectedType);
    if (viewMode === "by_size" && selectedSize !== null)
      return configs.filter((c) => c.story_points === selectedSize);
    return configs;
  }, [configs, viewMode, selectedType, selectedSize]);

  const makeLabel = useCallback(
    (c: PreviewConfigItem) => {
      if (viewMode === "by_type" && selectedType)
        return c.story_points === 0 ? "Default" : c.story_points + " SP";
      if (viewMode === "by_size" && selectedSize !== null)
        return c.issue_type;
      return `${c.issue_type} / ${c.story_points === 0 ? "Default" : c.story_points + " SP"}`;
    },
    [viewMode, selectedType, selectedSize],
  );

  const rowLabels = useMemo(
    () => [...new Set(filtered.map(makeLabel))],
    [filtered, makeLabel],
  );

  /* build segments */
  const segments = useMemo(() => {
    const result: SegmentInfo[] = [];
    for (let ri = 0; ri < rowLabels.length; ri++) {
      const label = rowLabels[ri];
      let cumX = 0;
      for (let si = 0; si < statuses.length; si++) {
        const matching = filtered.filter(
          (c) => makeLabel(c) === label && c.jira_status === statuses[si],
        );
        if (matching.length === 0) continue;
        const avg =
          matching.reduce((s, c) => s + (c.full_time_p50 ?? 0), 0) /
          matching.length;
        if (avg <= 0) { continue; }
        const cfg = matching[0];
        result.push({
          statusIdx: si,
          rowIdx: ri,
          status: statuses[si],
          workflowStepId: cfg.workflow_step_id,
          issueType: cfg.issue_type,
          storyPoints: cfg.story_points,
          xStart: cumX,
          width: avg,
        });
        cumX += avg;
      }
    }
    return result;
  }, [rowLabels, statuses, filtered, makeLabel]);

  /* scales */
  const plotW = width - MARGIN.left - MARGIN.right;
  const plotH = rowLabels.length * (BAR_HEIGHT + BAR_GAP);
  const chartH = plotH + MARGIN.top + MARGIN.bottom;

  const xMax = useMemo(() => {
    let max = 0;
    const rowTotals = new Map<number, number>();
    for (const seg of segments) {
      const total = (rowTotals.get(seg.rowIdx) ?? 0) + seg.width;
      rowTotals.set(seg.rowIdx, total);
      if (total > max) max = total;
    }
    // account for active drag
    if (drag) {
      const s = segments[drag.segIdx];
      if (s) {
        const delta = drag.currentWidth - s.width;
        const rowTotal = (rowTotals.get(s.rowIdx) ?? 0) + delta;
        if (rowTotal > max) max = rowTotal;
      }
    }
    return max * 1.1 || 10;
  }, [segments, drag]);

  const xScale = useCallback(
    (val: number) => (val / xMax) * plotW,
    [xMax, plotW],
  );
  const xInverse = useCallback(
    (px: number) => (px / plotW) * xMax,
    [xMax, plotW],
  );
  const yCenter = useCallback(
    (rowIdx: number) => rowIdx * (BAR_HEIGHT + BAR_GAP) + BAR_HEIGHT / 2,
    [],
  );

  const xTicks = useMemo(() => makeTicks(xMax), [xMax]);

  /* get segment width, accounting for drag */
  const getWidth = useCallback(
    (segIdx: number): number => {
      if (drag && drag.segIdx === segIdx) return drag.currentWidth;
      return segments[segIdx]?.width ?? 0;
    },
    [drag, segments],
  );

  /* compute cumulative xStart for rendering, accounting for drag */
  const getSegmentX = useCallback(
    (segIdx: number): number => {
      const seg = segments[segIdx];
      if (!seg) return 0;
      let x = 0;
      for (let i = 0; i < segments.length; i++) {
        const s = segments[i];
        if (s.rowIdx !== seg.rowIdx) continue;
        if (i === segIdx) return x;
        x += getWidth(i);
      }
      return x;
    },
    [segments, getWidth],
  );

  /* pointer handlers */
  const handlePointerDown = useCallback(
    (segIdx: number) => (e: React.PointerEvent) => {
      if (!onValueChange) return;
      (e.target as Element).setPointerCapture(e.pointerId);
      setDrag({ segIdx, currentWidth: segments[segIdx].width });
      e.preventDefault();
    },
    [onValueChange, segments],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!drag) return;
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const localX = e.clientX - rect.left - MARGIN.left;
      const seg = segments[drag.segIdx];
      if (!seg) return;
      const segX = getSegmentX(drag.segIdx);
      const newRight = xInverse(localX);
      const newWidth = Math.max(0.1, Math.round((newRight - segX) * 10) / 10);
      setDrag((prev) => (prev ? { ...prev, currentWidth: newWidth } : null));
    },
    [drag, xInverse, segments, getSegmentX],
  );

  const handlePointerUp = useCallback(() => {
    if (!drag || !onValueChange) return;
    const seg = segments[drag.segIdx];
    if (seg) {
      onValueChange(
        seg.workflowStepId,
        seg.issueType,
        seg.storyPoints,
        drag.currentWidth,
      );
    }
    setDrag(null);
  }, [drag, onValueChange, segments]);

  if (configs.length === 0) return null;

  return (
    <div className="rounded-lg border bg-card p-4">
      {/* header */}
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold">
          Expected Time in Status (p50, hours)
        </h3>
        {onValueChange && (
          <span className="text-[10px] text-muted-foreground">
            Drag edges to edit
          </span>
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
              if (!selectedType && issueTypes.length > 0)
                setSelectedType(issueTypes[0]);
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
              if (selectedSize === null && sizes.length > 0)
                setSelectedSize(sizes[0]);
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

      {/* chart */}
      <div ref={containerRef}>
        <svg
          ref={svgRef}
          width={width}
          height={chartH}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          style={{ userSelect: "none", touchAction: "none" }}
        >
          <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
            {/* x grid + ticks */}
            {xTicks.map((t) => (
              <g key={t} transform={`translate(${xScale(t)},0)`}>
                <line y1={0} y2={plotH} stroke="#e5e7eb" strokeWidth={1} />
                <text
                  y={plotH + 16}
                  textAnchor="middle"
                  fontSize={10}
                  fill="#6b7280"
                >
                  {t}
                </text>
              </g>
            ))}
            {/* x axis label */}
            <text
              x={plotW / 2}
              y={plotH + 32}
              textAnchor="middle"
              fontSize={11}
              fill="#6b7280"
            >
              Hours
            </text>

            {/* row labels */}
            {rowLabels.map((label, ri) => (
              <text
                key={label}
                x={-8}
                y={yCenter(ri)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={10}
                fill="#374151"
              >
                {label}
              </text>
            ))}

            {/* bar segments */}
            {segments.map((seg, si) => {
              const w = getWidth(si);
              const x = xScale(getSegmentX(si));
              const pxW = xScale(w);
              const y = yCenter(seg.rowIdx) - BAR_HEIGHT / 2;
              const color = STATUS_COLORS[seg.statusIdx % STATUS_COLORS.length];
              const isDragging = drag?.segIdx === si;

              return (
                <g key={si}>
                  {/* bar rect */}
                  <rect
                    x={x}
                    y={y}
                    width={Math.max(0, pxW)}
                    height={BAR_HEIGHT}
                    fill={color}
                    fillOpacity={0.75}
                    stroke={color}
                    strokeWidth={0.5}
                  />

                  {/* drag handle on right edge */}
                  {onValueChange && pxW > 4 && (
                    <rect
                      x={x + pxW - HANDLE_WIDTH / 2}
                      y={y}
                      width={HANDLE_WIDTH}
                      height={BAR_HEIGHT}
                      fill={isDragging ? "rgba(0,0,0,0.4)" : "rgba(0,0,0,0.15)"}
                      stroke={color}
                      strokeWidth={1.5}
                      rx={3}
                      cursor="ew-resize"
                      onPointerDown={handlePointerDown(si)}
                    />
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* legend */}
        <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
          {statuses.map((status, i) => (
            <div key={status} className="flex items-center gap-1">
              <div
                className="h-3 w-3 rounded-sm"
                style={{
                  backgroundColor: STATUS_COLORS[i % STATUS_COLORS.length],
                  opacity: 0.75,
                }}
              />
              <span className="text-xs text-muted-foreground">{status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
