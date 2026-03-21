import Plot from "react-plotly.js";
import type { TimingTemplateEntryInput } from "@/lib/types";

interface CycleTimeBoxPlotProps {
  entries: TimingTemplateEntryInput[];
}

export function CycleTimeBoxPlot({ entries }: CycleTimeBoxPlotProps) {
  if (entries.length === 0) return null;

  // Filter out entries with no data
  const validEntries = entries.filter((e) => e.ct_median > 0);
  if (validEntries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
        Enter cycle time values to see the distribution chart.
      </div>
    );
  }

  // Each entry becomes a box using the statistical values
  const data = validEntries.map((e) => ({
    type: "box" as const,
    name: `${e.issue_type} ${e.story_points === 0 ? "Def" : e.story_points + "SP"}`,
    lowerfence: [e.ct_min],
    q1: [e.ct_q1],
    median: [e.ct_median],
    q3: [e.ct_q3],
    upperfence: [e.ct_max],
    boxpoints: false as const,
  }));

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="mb-2 text-sm font-semibold">Cycle Time Distribution</h3>
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
