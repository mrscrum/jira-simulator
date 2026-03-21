import { useMemo, useState } from "react";
import Plot from "react-plotly.js";
import { Button } from "@/components/ui/button";
import type { PreviewConfigItem } from "@/lib/types";

type ViewMode = "all" | "by_type" | "by_size";

interface StatusDistributionChartProps {
  configs: PreviewConfigItem[];
}

// Color palette for statuses
const STATUS_COLORS = [
  "#60a5fa", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#94a3b8", "#4ade80",
];

export function StatusDistributionChart({ configs }: StatusDistributionChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedSize, setSelectedSize] = useState<number | null>(null);

  const issueTypes = useMemo(
    () => [...new Set(configs.map((c) => c.issue_type))].sort(),
    [configs],
  );
  const sizes = useMemo(
    () => [...new Set(configs.map((c) => c.story_points))].sort((a, b) => a - b),
    [configs],
  );
  const statuses = useMemo(() => {
    // Maintain order by status_category: todo first, then in_progress, then done
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

  // Build bars: each status is a trace, y-axis is "Type / Size"
  const yLabels = [...new Set(filtered.map((c) => {
    if (viewMode === "by_type" && selectedType) return `${c.story_points === 0 ? "Default" : c.story_points + " SP"}`;
    if (viewMode === "by_size" && selectedSize !== null) return c.issue_type;
    return `${c.issue_type} / ${c.story_points === 0 ? "Default" : c.story_points + " SP"}`;
  }))];

  const traces = statuses.map((status, i) => {
    const values = yLabels.map((label) => {
      // Find matching config for this label + status
      const matching = filtered.filter((c) => {
        let cLabel: string;
        if (viewMode === "by_type" && selectedType) {
          cLabel = c.story_points === 0 ? "Default" : c.story_points + " SP";
        } else if (viewMode === "by_size" && selectedSize !== null) {
          cLabel = c.issue_type;
        } else {
          cLabel = `${c.issue_type} / ${c.story_points === 0 ? "Default" : c.story_points + " SP"}`;
        }
        return cLabel === label && c.jira_status === status;
      });
      if (matching.length === 0) return 0;
      // Use p50 as the "average expected time"
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

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Expected Time in Status (p50, hours)</h3>
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
      />
    </div>
  );
}
