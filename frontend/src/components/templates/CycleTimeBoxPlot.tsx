import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { TimingTemplateEntryInput } from "@/lib/types";

const FIELDS = ["ct_min", "ct_q1", "ct_median", "ct_q3", "ct_max"] as const;
type BoxField = (typeof FIELDS)[number];
const FIELD_LABELS = ["Min", "Q1", "Median", "Q3", "Max"];

const COLORS = [
  "#60a5fa", "#fb923c", "#4ade80", "#f87171", "#a78bfa", "#fbbf24",
  "#2dd4bf", "#e879f9", "#94a3b8", "#34d399",
];

const MARGIN = { top: 12, right: 30, bottom: 42, left: 72 };
const ROW_HEIGHT = 48;
const ROW_GAP = 8;
const BOX_HEIGHT_RATIO = 0.55;
const HANDLE_R = 7;

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
  const [width, setWidth] = useState(0);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; label: string } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  /* working copy of entries that we mutate during drag for instant feedback */
  const [localEntries, setLocalEntries] = useState<TimingTemplateEntryInput[]>([]);
  useEffect(() => {
    if (!drag) setLocalEntries(entries);
  }, [entries, drag]);

  /* observe the wrapper div's width */
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => {
      const w = el.clientWidth;
      if (w > 0) setWidth(w);
    };
    // immediate read + rAF fallback for first layout
    update();
    requestAnimationFrame(update);
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* data filtering */
  const validEntries = useMemo(
    () => localEntries.filter((e) => e.ct_median > 0),
    [localEntries],
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
  const plotW = Math.max(1, width - MARGIN.left - MARGIN.right);
  const plotH = sorted.length * (ROW_HEIGHT + ROW_GAP);
  const chartH = plotH + MARGIN.top + MARGIN.bottom;
  const boxHalfH = (ROW_HEIGHT * BOX_HEIGHT_RATIO) / 2;

  const xExtent = useMemo(() => {
    if (sorted.length === 0) return { min: 0, max: 25 };
    let hi = -Infinity;
    for (const e of sorted) {
      if (e.ct_max > hi) hi = e.ct_max;
    }
    return { min: 0, max: Math.max(25, hi) };
  }, [sorted]);

  const xScale = useCallback(
    (val: number) => ((val - xExtent.min) / (xExtent.max - xExtent.min)) * plotW,
    [xExtent, plotW],
  );
  const xInverse = useCallback(
    (px: number) => xExtent.min + (px / plotW) * (xExtent.max - xExtent.min),
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

  /* pointer handlers */
  const handlePointerDown = useCallback(
    (entryIdx: number, fieldIdx: number) => (e: React.PointerEvent) => {
      if (!onEntryChange) return;
      (e.target as Element).setPointerCapture(e.pointerId);
      const entry = sorted[entryIdx];
      setDrag({ entryIdx, fieldIdx });
      setTooltip({
        x: e.clientX,
        y: e.clientY,
        label: `${FIELD_LABELS[fieldIdx]}: ${entry[FIELDS[fieldIdx]]}h`,
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
      const localX = e.clientX - rect.left - MARGIN.left;
      const raw = xInverse(localX);
      const clamped = Math.max(0, Math.round(raw * 10) / 10);

      setLocalEntries((prev) => {
        const entry = sorted[drag.entryIdx];
        if (!entry) return prev;
        const idx = prev.findIndex(
          (p) => p.issue_type === entry.issue_type && p.story_points === entry.story_points,
        );
        if (idx === -1) return prev;

        const vals = FIELDS.map((f) => prev[idx][f]);
        vals[drag.fieldIdx] = clamped;

        // enforce ordering: min <= q1 <= median <= q3 <= max
        for (let i = drag.fieldIdx - 1; i >= 0; i--) {
          if (vals[i] > vals[i + 1]) vals[i] = vals[i + 1];
        }
        for (let i = drag.fieldIdx + 1; i < vals.length; i++) {
          if (vals[i] < vals[i - 1]) vals[i] = vals[i - 1];
        }

        const next = [...prev];
        next[idx] = {
          ...next[idx],
          ct_min: vals[0],
          ct_q1: vals[1],
          ct_median: vals[2],
          ct_q3: vals[3],
          ct_max: vals[4],
        };
        return next;
      });

      setTooltip({
        x: e.clientX,
        y: e.clientY,
        label: `${FIELD_LABELS[drag.fieldIdx]}: ${clamped}h`,
      });
    },
    [drag, xInverse, sorted],
  );

  const handlePointerUp = useCallback(() => {
    if (!drag || !onEntryChange) {
      setDrag(null);
      setTooltip(null);
      return;
    }

    // commit all changed fields from localEntries back to parent
    const entry = sorted[drag.entryIdx];
    if (entry) {
      const localEntry = localEntries.find(
        (p) => p.issue_type === entry.issue_type && p.story_points === entry.story_points,
      );
      if (localEntry) {
        for (const field of FIELDS) {
          if (localEntry[field] !== entry[field]) {
            onEntryChange(entry.issue_type, entry.story_points, field, localEntry[field]);
          }
        }
      }
    }

    setDrag(null);
    setTooltip(null);
  }, [drag, onEntryChange, sorted, localEntries]);

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
      <div ref={wrapRef} className="relative">
        <svg
          ref={svgRef}
          height={chartH}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={() => { setDrag(null); setTooltip(null); }}
          style={{ width: "100%", display: "block", userSelect: "none", touchAction: "none" }}
        >
          {width > 0 && (
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
                const vMin = entry.ct_min;
                const vQ1 = entry.ct_q1;
                const vMed = entry.ct_median;
                const vQ3 = entry.ct_q3;
                const vMax = entry.ct_max;
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

                    {/* row background */}
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
                    {/* min cap */}
                    <line
                      x1={xScale(vMin)}
                      y1={cy - boxHalfH * 0.5}
                      x2={xScale(vMin)}
                      y2={cy + boxHalfH * 0.5}
                      stroke={color}
                      strokeWidth={1.5}
                    />
                    {/* max cap */}
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
                      width={Math.max(0, xScale(vQ3) - xScale(vQ1))}
                      height={boxHalfH * 2}
                      fill={color}
                      fillOpacity={0.22}
                      stroke={color}
                      strokeWidth={1.5}
                      rx={3}
                    />
                    {/* median line */}
                    <line
                      x1={xScale(vMed)}
                      y1={cy - boxHalfH}
                      x2={xScale(vMed)}
                      y2={cy + boxHalfH}
                      stroke={color}
                      strokeWidth={2.5}
                    />

                    {/* drag handles */}
                    {onEntryChange &&
                      FIELDS.map((_, fi) => {
                        const v = entry[FIELDS[fi]];
                        const isDragging =
                          drag?.entryIdx === ei && drag?.fieldIdx === fi;
                        return (
                          <circle
                            key={fi}
                            cx={xScale(v)}
                            cy={cy}
                            r={isDragging ? HANDLE_R + 2 : HANDLE_R}
                            fill={color}
                            fillOpacity={isDragging ? 1 : 0.35}
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
          )}
        </svg>

        {/* floating tooltip during drag */}
        {tooltip && drag && (
          <div
            className="pointer-events-none fixed z-50 rounded bg-gray-900 px-2 py-1 text-xs text-white shadow-lg"
            style={{
              left: tooltip.x + 14,
              top: tooltip.y - 30,
            }}
          >
            {tooltip.label}
          </div>
        )}
      </div>

      {/* values table */}
      {sorted.length > 0 && (
        <table className="mt-4 w-full text-xs" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr className="border-b text-[10px] text-muted-foreground">
              <th className="py-1 text-left font-medium">Size</th>
              <th className="py-1 text-center font-medium">Min</th>
              <th className="py-1 text-center font-medium">Q1</th>
              <th className="py-1 text-center font-medium">Median</th>
              <th className="py-1 text-center font-medium">Q3</th>
              <th className="py-1 text-center font-medium">Max</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((entry) => (
              <tr
                key={`${entry.issue_type}-${entry.story_points}`}
                className="border-b border-muted/40"
              >
                <td className="py-1 font-medium">
                  {entry.story_points === 0 ? "Default" : `${entry.story_points} SP`}
                </td>
                {FIELDS.map((f) => (
                  <td key={f} className="py-1 text-center tabular-nums">
                    {entry[f]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
