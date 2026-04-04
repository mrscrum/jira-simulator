import { useState } from "react";
import { useFlowMatrix } from "@/hooks/useScheduledEvents";

interface FlowMatrixProps {
  teamId: number;
  sprintId: number;
}

type ViewMode = "items" | "points";

function getCellColor(value: number, maxValue: number): string {
  if (maxValue === 0 || value === 0) return "";
  const intensity = value / maxValue;
  if (intensity > 0.6) return "bg-orange-100";
  if (intensity > 0.3) return "bg-amber-50";
  return "bg-emerald-50";
}

function getChangeIndicator(current: number, previous: number | undefined): string {
  if (previous === undefined) return "\u2013"; // dash for first day
  if (current > previous) return "\u2191"; // up arrow
  if (current < previous) return "\u2193"; // down arrow
  return "\u2013"; // dash for no change
}

function getChangeColor(current: number, previous: number | undefined): string {
  if (previous === undefined) return "text-muted-foreground";
  if (current > previous) return "text-red-500";
  if (current < previous) return "text-green-500";
  return "text-muted-foreground";
}

export function FlowMatrix({ teamId, sprintId }: FlowMatrixProps) {
  const { data, isLoading, error } = useFlowMatrix(teamId, sprintId);
  const [viewMode, setViewMode] = useState<ViewMode>("items");

  if (isLoading) {
    return <div className="py-8 text-center text-muted-foreground">Loading flow matrix...</div>;
  }

  if (error) {
    return (
      <div className="py-8 text-center text-red-600">
        Failed to load flow matrix: {(error as Error)?.message ?? "Unknown error"}
      </div>
    );
  }

  if (!data || data.days.length === 0 || data.statuses.length === 0) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        No flow data available. Pre-compute a sprint to see the flow matrix.
      </div>
    );
  }

  const grid = viewMode === "items" ? data.items : data.points;
  const maxValue = Math.max(...grid.flat(), 1);
  const unit = viewMode === "points" ? "SP" : "";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Flow over days matrix</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode("items")}
            className={`rounded-md px-3 py-1 text-sm ${
              viewMode === "items"
                ? "bg-blue-600 text-white"
                : "border hover:bg-accent"
            }`}
          >
            Items
          </button>
          <button
            onClick={() => setViewMode("points")}
            className={`rounded-md px-3 py-1 text-sm ${
              viewMode === "points"
                ? "bg-blue-600 text-white"
                : "border hover:bg-accent"
            }`}
          >
            Story Points
          </button>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Status-by-status occupancy with movement direction and duration intensity.
      </p>

      <div className="overflow-auto rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left font-medium sticky left-0 bg-muted/50 z-10">
                Status
              </th>
              {data.days.map((day) => (
                <th key={day} className="px-4 py-2 text-center font-medium whitespace-nowrap">
                  {day}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.statuses.map((status, statusIdx) => (
              <tr key={status} className="border-b">
                <td className="px-3 py-2 font-medium sticky left-0 bg-background z-10 whitespace-nowrap">
                  {status}
                </td>
                {data.days.map((_, dayIdx) => {
                  const value = grid[statusIdx][dayIdx];
                  const prevValue = dayIdx > 0 ? grid[statusIdx][dayIdx - 1] : undefined;
                  const cellBg = getCellColor(value, maxValue);
                  const indicator = getChangeIndicator(value, prevValue);
                  const indicatorColor = getChangeColor(value, prevValue);

                  return (
                    <td
                      key={dayIdx}
                      className={`px-4 py-2 text-center ${cellBg}`}
                    >
                      <div className="flex items-center justify-center gap-1">
                        <span className="tabular-nums font-medium">
                          {value}{unit ? ` ${unit}` : ""}
                        </span>
                        <span className={`text-xs ${indicatorColor}`}>
                          {indicator}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <span className="inline-block w-4 h-4 rounded bg-emerald-50 border"></span>
          Low duration
        </div>
        <div className="flex items-center gap-1">
          <span className="inline-block w-4 h-4 rounded bg-amber-50 border"></span>
          Medium duration
        </div>
        <div className="flex items-center gap-1">
          <span className="inline-block w-4 h-4 rounded bg-orange-100 border"></span>
          High duration (possible bottleneck)
        </div>
        <span>
          <span className="text-red-500">&uarr;</span> Increased
          <span className="mx-2 text-green-500">&darr;</span> Decreased
          <span className="mx-2">&ndash;</span> No change
        </span>
      </div>
    </div>
  );
}
