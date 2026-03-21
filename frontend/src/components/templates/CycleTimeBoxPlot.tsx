import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import Plot from "./PlotlyChart";
import type { TimingTemplateEntryInput } from "@/lib/types";

interface CycleTimeBoxPlotProps {
  entries: TimingTemplateEntryInput[];
}

export function CycleTimeBoxPlot({ entries }: CycleTimeBoxPlotProps) {
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const validEntries = useMemo(
    () => entries.filter((e) => e.ct_median > 0),
    [entries],
  );

  const issueTypes = useMemo(
    () => [...new Set(validEntries.map((e) => e.issue_type))].sort(),
    [validEntries],
  );

  // Auto-select first type when types change
  const activeType = selectedType && issueTypes.includes(selectedType)
    ? selectedType
    : issueTypes[0] ?? null;

  if (validEntries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
        Enter cycle time values to see the distribution chart.
      </div>
    );
  }

  const filtered = activeType
    ? validEntries.filter((e) => e.issue_type === activeType)
    : validEntries;

  const data = filtered.map((e) => ({
    type: "box" as const,
    name: e.story_points === 0 ? "Default" : `${e.story_points} SP`,
    lowerfence: [e.ct_min],
    q1: [e.ct_q1],
    median: [e.ct_median],
    q3: [e.ct_q3],
    upperfence: [e.ct_max],
    boxpoints: false as const,
  }));

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Cycle Time Distribution</h3>
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
      <Plot
        data={data}
        layout={{
          height: 300,
          margin: { t: 20, b: 60, l: 50, r: 20 },
          yaxis: { title: { text: "Hours" }, zeroline: true },
          xaxis: { tickangle: -45 },
          showlegend: false,
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { size: 11 },
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
