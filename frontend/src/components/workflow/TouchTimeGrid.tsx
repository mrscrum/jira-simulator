import { Input } from "@/components/ui/input";
import type { TouchTimeConfigInput } from "@/lib/types";

const ISSUE_TYPES = ["Story", "Bug", "Task"];
const STORY_POINTS = [1, 2, 3, 5, 8, 13];

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
    field: "min_hours" | "max_hours",
    value: string,
  ) => {
    const num = parseFloat(value) || 0;
    const existing = getConfig(issueType, sp);
    const updated = existing
      ? configs.map((c) =>
          c.issue_type === issueType && c.story_points === sp
            ? { ...c, [field]: num }
            : c,
        )
      : [
          ...configs,
          {
            issue_type: issueType,
            story_points: sp,
            min_hours: field === "min_hours" ? num : 0,
            max_hours: field === "max_hours" ? num : 0,
          },
        ];
    onChange(updated);
  };

  return (
    <div className="overflow-auto" data-testid="touch-time-grid">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="px-1 py-0.5 text-left font-medium">Type</th>
            {STORY_POINTS.map((sp) => (
              <th key={sp} className="px-1 py-0.5 text-center font-medium">
                {sp} SP
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ISSUE_TYPES.map((type) => (
            <tr key={type}>
              <td className="px-1 py-0.5">{type}</td>
              {STORY_POINTS.map((sp) => {
                const cfg = getConfig(type, sp);
                return (
                  <td key={sp} className="px-0.5 py-0.5">
                    <div className="flex items-center gap-0.5">
                      <Input
                        type="number"
                        min="0"
                        step="0.5"
                        className="h-7 w-9 px-1 text-center text-xs"
                        value={cfg?.min_hours ?? ""}
                        onChange={(e) =>
                          updateConfig(type, sp, "min_hours", e.target.value)
                        }
                        placeholder="min"
                      />
                      <span className="text-muted-foreground">&ndash;</span>
                      <Input
                        type="number"
                        min="0"
                        step="0.5"
                        className="h-7 w-9 px-1 text-center text-xs"
                        value={cfg?.max_hours ?? ""}
                        onChange={(e) =>
                          updateConfig(type, sp, "max_hours", e.target.value)
                        }
                        placeholder="max"
                      />
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
