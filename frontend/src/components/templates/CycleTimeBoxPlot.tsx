import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { TimingTemplateEntryInput } from "@/lib/types";

const FIELDS = ["ct_min", "ct_q1", "ct_median", "ct_q3", "ct_max"] as const;
type BoxField = (typeof FIELDS)[number];

const COLORS = [
  "#60a5fa", "#fb923c", "#4ade80", "#f87171", "#a78bfa",
  "#fbbf24", "#2dd4bf", "#e879f9", "#94a3b8", "#34d399",
];

const MARGIN = { top: 20, right: 20, bottom: 50, left: 55 };
const CHART_HEIGHT = 300;
const HANDLE_R = 7;
const BOX_WIDTH_RATIO = 0.5; // fraction of band width

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

function makeTicks(min: number, max: number, target = 6): number[] {
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

  /* scales */
  const plotW = width - MARGIN.left - MARGIN.right;
  const plotH = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;

  const yExtent = useMemo(() => {
    if (sorted.length === 0) return { min: 0, max: 10 };
    let lo = Infinity,
      hi = -Infinity;
    for (const e of sorted) {
      if (e.ct_min < lo) lo = e.ct_min;
      if (e.ct_max > hi) hi = e.ct_max;
    }
    const pad = (hi - lo) * 0.15 || 1;
    return { min: Math.max(0, lo - pad), max: hi + pad };
  }, [sorted]);

  const yScale = useCallback(
    (val: number) => {
      const { min, max } = yExtent;
      return plotH - ((val - min) / (max - min)) * plotH;
    },
    [yExtent, plotH],
  );
  const yInverse = useCallback(
    (py: number) => {
      const { min, max } = yExtent;
      return min + ((plotH - py) / plotH) * (max - min);
    },
    [yExtent, plotH],
  );

  const bandW = sorted.length > 0 ? plotW / sorted.length : plotW;
  const xCenter = useCallback(
    (idx: number) => idx * bandW + bandW / 2,
    [bandW],
  );
  const boxHalfW = (bandW * BOX_WIDTH_RATIO) / 2;

  const yTicks = useMemo(
    () => makeTicks(yExtent.min, yExtent.max),
    [yExtent],
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

  /* pointer handlers */
  const handlePointerDown = useCallback(
    (entryIdx: number, fieldIdx: number) => (e: React.PointerEvent) => {
      if (!onEntryChange) return;
      (e.target as Element).setPointerCapture(e.pointerId);
      setDrag({
        entryIdx,
        fieldIdx,
        currentValue: sorted[entryIdx][FIELDS[fieldIdx]],
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
      const localY = e.clientY - rect.top - MARGIN.top;
      const raw = yInverse(localY);
      const clamped = Math.max(0, Math.round(raw * 10) / 10);
      setDrag((prev) => (prev ? { ...prev, currentValue: clamped } : null));
    },
    [drag, yInverse],
  );

  const handlePointerUp = useCallback(() => {
    if (!drag || !onEntryChange) return;
    const entry = sorted[drag.entryIdx];
    if (!entry) {
      setDrag(null);
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
      <div ref={containerRef}>
        <svg
          ref={svgRef}
          width={width}
          height={CHART_HEIGHT}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          style={{ userSelect: "none", touchAction: "none" }}
        >
          <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
            {/* grid + y axis */}
            {yTicks.map((t) => (
              <g key={t} transform={`translate(0,${yScale(t)})`}>
                <line x1={0} x2={plotW} stroke="#e5e7eb" strokeWidth={1} />
                <text
                  x={-8}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontSize={10}
                  fill="#6b7280"
                >
                  {t}
                </text>
              </g>
            ))}
            {/* y axis label */}
            <text
              transform={`translate(-40,${plotH / 2}) rotate(-90)`}
              textAnchor="middle"
              fontSize={11}
              fill="#6b7280"
            >
              Hours
            </text>

            {/* box plots */}
            {sorted.map((entry, ei) => {
              const cx = xCenter(ei);
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
                  {/* whisker line min→max */}
                  <line
                    x1={cx}
                    y1={yScale(vMin)}
                    x2={cx}
                    y2={yScale(vMax)}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* min cap */}
                  <line
                    x1={cx - boxHalfW * 0.5}
                    y1={yScale(vMin)}
                    x2={cx + boxHalfW * 0.5}
                    y2={yScale(vMin)}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* max cap */}
                  <line
                    x1={cx - boxHalfW * 0.5}
                    y1={yScale(vMax)}
                    x2={cx + boxHalfW * 0.5}
                    y2={yScale(vMax)}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* box q1→q3 */}
                  <rect
                    x={cx - boxHalfW}
                    y={yScale(vQ3)}
                    width={boxHalfW * 2}
                    height={yScale(vQ1) - yScale(vQ3)}
                    fill={color}
                    fillOpacity={0.3}
                    stroke={color}
                    strokeWidth={1.5}
                  />
                  {/* median line */}
                  <line
                    x1={cx - boxHalfW}
                    y1={yScale(vMed)}
                    x2={cx + boxHalfW}
                    y2={yScale(vMed)}
                    stroke={color}
                    strokeWidth={2}
                  />

                  {/* x axis label */}
                  <text
                    x={cx}
                    y={plotH + 20}
                    textAnchor="middle"
                    fontSize={10}
                    fill="#6b7280"
                  >
                    {label}
                  </text>

                  {/* drag handles */}
                  {onEntryChange &&
                    FIELDS.map((_, fi) => {
                      const v = getVal(ei, fi);
                      const isDragging =
                        drag?.entryIdx === ei && drag?.fieldIdx === fi;
                      return (
                        <circle
                          key={fi}
                          cx={cx}
                          cy={yScale(v)}
                          r={isDragging ? HANDLE_R + 2 : HANDLE_R}
                          fill={
                            isDragging
                              ? color
                              : `${color}66`
                          }
                          stroke={color}
                          strokeWidth={isDragging ? 2.5 : 1.5}
                          cursor="ns-resize"
                          onPointerDown={handlePointerDown(ei, fi)}
                        />
                      );
                    })}
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    </div>
  );
}
