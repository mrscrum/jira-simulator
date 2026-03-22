import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { TimingTemplateEntryInput } from "@/lib/types";

const FIELDS = ["ct_min", "ct_q1", "ct_median", "ct_q3", "ct_max"] as const;
type BoxField = (typeof FIELDS)[number];
const FIELD_LABELS = ["Min", "Q1", "Median", "Q3", "Max"];

const COLORS = [
  "#60a5fa", "#fb923c", "#4ade80", "#f87171", "#a78bfa",
  "#fbbf24", "#2dd4bf", "#e879f9", "#94a3b8", "#34d399",
];

const MARGIN = { top: 10, right: 30, bottom: 40, left: 80 };
const ROW_HEIGHT = 48;
const ROW_GAP = 8;
const BOX_HEIGHT_RATIO = 0.55;
const HANDLE_R = 8;

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
  entryIdx: number;
  fieldIdx: number;
  currentValue: number;
}

/* ---------- axis helpers ---------- */

function niceStep(range: number, targetTicks: number): number {
  const raw = range / targetTicks;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const nice = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  return nice * mag;
}

function makeTicks(min: number, max: number, target = 8): number[] {
  if (max <= min) return [0];
  const step = niceStep(max - min, target);
  const start = Math.floor(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.01; v += step) {
    ticks.push(Math.round(v * 1e6) / 1e6);
  }
  return ticks;
}

export function CycleTimeBoxPlot({ entries, onEntryChange }: CycleTimeBoxPlotProps) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [width, setWidth] = useState(800);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; label: string } | null>(null);
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

  /* data filtering */
  const validEntries = useMemo(
    () => entries.filter((e) => e.ct_median > 0),
    [entries],
  );
  const issueTypes = useMemo(
    () => [...new Set(validEntries.map((e) => e.issue_type))].sort(),
    [validEntries],
  );
  const activeType =
    selectedType && issueTypes.includes(selectedType)
      ? selectedType
      : issueTypes[0] ?? null;
  const filtered = activeType
    ? validEntries.filter((e) => e.issue_type === activeType)
    : validEntries;
  const sorted = useMemo(
    () => [...filtered].sort((a, b) => a.story_points - b.story_points),
    [filtered],
  );

  /* scales — HORIZONTAL: x = value (Hours), y = category bands */
  const plotW = width - MARGIN.left - MARGIN.right;
  const plotH = sorted.length * (ROW_HEIGHT + ROW_GAP);
  const chartH = plotH + MARGIN.top + MARGIN.bottom;
  const boxHalfH = (ROW_HEIGHT * BOX_HEIGHT_RATIO) / 2;

  const xExtent = useMemo(() => {
    if (sorted.length === 0) return { min: 0, max: 25 };
    let hi = -Infinity;
    for (const e of sorted) {
      if (e.ct_max > hi) hi = e.ct_max;
    }
    // Fixed at 25h; if data exceeds 25, scale up to fit
    return { min: 0, max: Math.max(25, hi) };
  }, [sorted]);

  const xScale = useCallback(
    (val: number) => {
      const { min, max } = xExtent;
      return ((val - min) / (max - min)) * plotW;
    },
    [xExtent, plotW],
  );
  const xInverse = useCallback(
    (px: number) => {
      const { min, max } = xExtent;
      return min + (px / plotW) * (max - min);
    },
    [xExtent, plotW],
  );

  const yCenter = useCallback(
    (idx: number) => idx * (ROW_HEIGHT + ROW_GAP) + ROW_HEIGHT / 2,
    [],
  );

  const xTicks = useMemo(
    () => makeTicks(xExtent.min, xExtent.max),
    [xExtent],
  );

  /* get value for a field, accounting for active drag */
  const getVal = useCallback(
    (entryIdx: number, fieldIdx: number): number => {
      if (drag && drag.entryIdx === entryIdx && drag.fieldIdx === fieldIdx) {
        return drag.currentValue;
      }
      return sorted[entryIdx]?.[FIELDS[fieldIdx]] ?? 0;
    },
    [drag, sorted],
  );

  /* pointer handlers — horizontal drag */
  const handlePointerDown = useCallback(
    (entryIdx: number, fieldIdx: number) => (e: React.PointerEvent) => {
      if (!onEntryChange) return;
      (e.target as Element).setPointerCapture(e.pointerId);
      const val = sorted[entryIdx][FIELDS[fieldIdx]];
      setDrag({ entryIdx, fieldIdx, currentValue: val });
      setTooltip({
        x: e.clientX,
        y: e.clientY,
        label: `${FIELD_LABELS[fieldIdx]}: ${val}h`,
      });
      e.preventDefault();
    },
    [onEntryChange, sorted],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!drag) return;
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      const scale = width / rect.width;
      const localX = (e.clientX - rect.left) * scale - MARGIN.left;
      const raw = xInverse(localX);
      const clamped = Math.max(0, Math.round(raw * 10) / 10);
      setDrag((prev) => (prev ? { ...prev, currentValue: clamped } : null));
      setTooltip({
        x: e.clientX,
        y: e.clientY,
        label: `${FIELD_LABELS[drag.fieldIdx]}: ${clamped}h`,
      });
    },
    [drag, xInverse],
  );

  const handlePointerUp = useCallback(() => {
    if (!drag || !onEntryChange) return;
    const entry = sorted[drag.entryIdx];
    if (!entry) {
      setDrag(null);
      setTooltip(null);
      return;
    }

    const vals = FIELDS.map((f) => entry[f]);
    vals[drag.fieldIdx] = drag.currentValue;

    // enforce ordering: min <= q1 <= median <= q3 <= max
    for (let i = drag.fieldIdx - 1; i >= 0; i--) {
      if (vals[i] > vals[i + 1]) vals[i] = vals[i + 1];
    }
    for (let i = drag.fieldIdx + 1; i < vals.length; i++) {
      if (vals[i] < vals[i - 1]) vals[i] = vals[i - 1];
    }
    for (let i = 0; i < FIELDS.length; i++) {
      if (vals[i] !== entry[FIELDS[i]]) {
        onEntryChange(entry.issue_type, entry.story_points, FIELDS[i], vals[i]);
      }
    }
    setDrag(null);
    setTooltip(null);
  }, [drag, onEntryChange, sorted]);

  if (validEntries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
        Enter cycle time values to see the distribution chart.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      {/* header */}
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Cycle Time Distribution</h3>
        {onEntryChange && (
          <span className="text-[10px] text-muted-foreground">
            Drag handles to edit
          </span>
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

      {/* chart */}
      <div ref={containerRef} className="relative w-full">
        <svg
          ref={svgRef}
          width="100%"
          height={chartH}
          viewBox={`0 0 ${width} ${chartH}`}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          style={{ userSelect: "none", touchAction: "none", display: "block" }}
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
              y={plotH + 34}
              textAnchor="middle"
              fontSize={11}
              fill="#6b7280"
            >
              Business Hours
            </text>

            {/* horizontal box plots */}
            {sorted.map((entry, ei) => {
              const cy = yCenter(ei);
              const color = COLORS[ei % COLORS.length];
              const vMin = getVal(ei, 0);
              const vQ1 = getVal(ei, 1);
              const vMed = getVal(ei, 2);
              const vQ3 = getVal(ei, 3);
              const vMax = getVal(ei, 4);
              const label =
                entry.story_points === 0
                  ? "Default"
                  : `${entry.story_points} SP`;

              return (
                <g key={`${entry.issue_type}-${entry.story_points}`}>
                  {/* row label */}
                  <text
                    x={-10}
                    y={cy}
                    textAnchor="end"
                    dominantBaseline="middle"
                    fontSize={11}
                    fill="#374151"
                  >
                    {label}
                  </text>

                  {/* row background for hover clarity */}
                  <rect
                    x={0}
                    y={cy - ROW_HEIGHT / 2}
                    width={plotW}
                    height={ROW_HEIGHT}
                    fill={color}
                    fillOpacity={0.04}
                    rx={4}
                  />

                  {/* whisker line min→max */}
                  <line
                    x1={xScale(vMin)}
                    y1={cy}
                    x2={xScale(vMax)}
                    y2={cy}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* min cap (vertical) */}
                  <line
                    x1={xScale(vMin)}
                    y1={cy - boxHalfH * 0.5}
                    x2={xScale(vMin)}
                    y2={cy + boxHalfH * 0.5}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* max cap (vertical) */}
                  <line
                    x1={xScale(vMax)}
                    y1={cy - boxHalfH * 0.5}
                    x2={xScale(vMax)}
                    y2={cy + boxHalfH * 0.5}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* box q1→q3 */}
                  <rect
                    x={xScale(vQ1)}
                    y={cy - boxHalfH}
                    width={xScale(vQ3) - xScale(vQ1)}
                    height={boxHalfH * 2}
                    fill={color}
                    fillOpacity={0.25}
                    stroke={color}
                    strokeWidth={1.5}
                    rx={2}
                  />
                  {/* median line (vertical) */}
                  <line
                    x1={xScale(vMed)}
                    y1={cy - boxHalfH}
                    x2={xScale(vMed)}
                    y2={cy + boxHalfH}
                    stroke={color}
                    strokeWidth={2.5}
                  />

                  {/* drag handles — circles on each parameter */}
                  {onEntryChange &&
                    FIELDS.map((_, fi) => {
                      const v = getVal(ei, fi);
                      const isDragging =
                        drag?.entryIdx === ei && drag?.fieldIdx === fi;
                      return (
                        <circle
                          key={fi}
                          cx={xScale(v)}
                          cy={cy}
                          r={isDragging ? HANDLE_R + 2 : HANDLE_R}
                          fill={isDragging ? color : `${color}55`}
                          stroke={color}
                          strokeWidth={isDragging ? 2.5 : 1.5}
                          cursor="ew-resize"
                          onPointerDown={handlePointerDown(ei, fi)}
                        />
                      );
                    })}
                </g>
              );
            })}
          </g>
        </svg>

        {/* floating tooltip during drag */}
        {tooltip && drag && (
          <div
            className="pointer-events-none fixed z-50 rounded bg-gray-900 px-2 py-1 text-xs text-white shadow-lg"
            style={{
              left: tooltip.x + 12,
              top: tooltip.y - 28,
            }}
          >
            {tooltip.label}
          </div>
        )}
      </div>
    </div>
  );
}
