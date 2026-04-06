import { Input } from "@/components/ui/input";
import type { TouchTimeConfigInput } from "@/lib/types";

const ISSUE_TYPES = ["Story", "Bug", "Task", "Spike", "Enabler"];
const STORY_POINTS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13];

type ConfigField = keyof Pick<
  TouchTimeConfigInput,
  "min_hours" | "max_hours" | "full_time_p25" | "full_time_p50" | "full_time_p99"
>;

interface TouchTimeGridProps {
  configs: TouchTimeConfigInput[];
  onChange: (configs: TouchTimeConfigInput[]) => void;
}

export function TouchTimeGrid({ configs, onChange }: TouchTimeGridProps) {
  const getConfig = (issueType: string, sp: number) =>
    configs.find((c) => c.issue_type === issueType && c.story_points === sp);

  const updateConfig = (
    issueType: string,
    sp: number,
    field: ConfigField,
    value: string,
  ) => {
    const num = parseFloat(value) || 0;
    const existing = getConfig(issueType, sp);
    if (existing) {
      onChange(
        configs.map((c) =>
          c.issue_type === issueType && c.story_points === sp
            ? { ...c, [field]: num }
            : c,
        ),
      );
    } else {
      onChange([
        ...configs,
        {
          issue_type: issueType,
          story_points: sp,
          min_hours: field === "min_hours" ? num : 0,
          max_hours: field === "max_hours" ? num : 0,
          full_time_p25: field === "full_time_p25" ? num : null,
          full_time_p50: field === "full_time_p50" ? num : null,
          full_time_p99: field === "full_time_p99" ? num : null,
        },
      ]);
    }
  };

  return (
    <div className="overflow-auto" data-testid="touch-time-grid">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="px-1 py-0.5 text-left font-medium">Type</th>
            {STORY_POINTS.map((sp) => (
              <th key={sp} className="px-1 py-0.5 text-center font-medium">
                {sp === 0 ? "Default" : `${sp} SP`}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ISSUE_TYPES.map((type) => (
            <tr key={type} className="border-t">
              <td className="px-1 py-1 align-top font-medium">{type}</td>
              {STORY_POINTS.map((sp) => {
                const cfg = getConfig(type, sp);
                return (
                  <td key={sp} className="px-0.5 py-1 align-top">
                    <div className="space-y-0.5">
                      {/* Work time: min–max */}
                      <div className="flex items-center gap-0.5">
                        <Input
                          type="number"
                          min="0"
                          step="0.5"
                          className="h-6 w-10 px-1 text-center text-xs"
                          value={cfg?.min_hours ?? ""}
                          onChange={(e) =>
                            updateConfig(type, sp, "min_hours", e.target.value)
                          }
                          placeholder="min"
                          title="Work time min (hours)"
                        />
                        <span className="text-muted-foreground">&ndash;</span>
                        <Input
                          type="number"
                          min="0"
                          step="0.5"
                          className="h-6 w-10 px-1 text-center text-xs"
                          value={cfg?.max_hours ?? ""}
                          onChange={(e) =>
                            updateConfig(type, sp, "max_hours", e.target.value)
                          }
                          placeholder="max"
                          title="Work time max (hours)"
                        />
                      </div>
                      {/* Full time: p25 / p50 / p99 */}
                      <div className="flex items-center gap-0.5">
                        <Input
                          type="number"
                          min="0"
                          step="0.5"
                          className="h-6 w-8 px-0.5 text-center text-xs text-blue-600"
                          value={cfg?.full_time_p25 ?? ""}
                          onChange={(e) =>
                            updateConfig(type, sp, "full_time_p25", e.target.value)
                          }
                          placeholder="p25"
                          title="Full time p25 (hours)"
                        />
                        <Input
                          type="number"
                          min="0"
                          step="0.5"
                          className="h-6 w-8 px-0.5 text-center text-xs text-blue-600"
                          value={cfg?.full_time_p50 ?? ""}
                          onChange={(e) =>
                            updateConfig(type, sp, "full_time_p50", e.target.value)
                          }
                          placeholder="p50"
                          title="Full time p50 (hours)"
                        />
                        <Input
                          type="number"
                          min="0"
                          step="0.5"
                          className="h-6 w-8 px-0.5 text-center text-xs text-blue-600"
                          value={cfg?.full_time_p99 ?? ""}
                          onChange={(e) =>
                            updateConfig(type, sp, "full_time_p99", e.target.value)
                          }
                          placeholder="p99"
                          title="Full time p99 (hours)"
                        />
                      </div>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-1 flex gap-4 text-[10px] text-muted-foreground">
        <span>Top row: work time (min–max)</span>
        <span className="text-blue-600">Bottom row: full time (p25 / p50 / p99)</span>
      </div>
    </div>
  );
}
