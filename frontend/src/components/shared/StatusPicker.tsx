import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useJiraStatuses } from "@/hooks/useJiraStatuses";

const CATEGORY_COLORS: Record<string, string> = {
  new: "bg-gray-200 text-gray-700",
  indeterminate: "bg-blue-200 text-blue-700",
  done: "bg-green-200 text-green-700",
};

interface StatusPickerProps {
  projectKey: string;
  value: string;
  onChange: (status: string) => void;
}

export function StatusPicker({ projectKey, value, onChange }: StatusPickerProps) {
  const { data: statuses = [], isLoading, isError, refetch } = useJiraStatuses(projectKey);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = statuses.filter((s) =>
    s.name.toLowerCase().includes(filter.toLowerCase()),
  );

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Loading statuses...</div>;
  }

  if (isError) {
    return (
      <div className="space-y-1">
        <p className="text-sm text-destructive">
          Could not load Jira statuses — check project key and credentials
        </p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="relative">
      <Input
        value={open ? filter : value}
        onChange={(e) => {
          setFilter(e.target.value);
          if (!open) setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Select Jira status..."
        data-testid="status-picker-input"
      />
      {open && (
        <div className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-md border bg-popover shadow-md">
          {filtered.length === 0 ? (
            <div className="p-2 text-sm text-muted-foreground">No statuses found</div>
          ) : (
            filtered.map((s) => (
              <button
                key={s.name}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-accent"
                onClick={() => {
                  onChange(s.name);
                  setFilter("");
                  setOpen(false);
                }}
                data-testid={`status-option-${s.name}`}
              >
                {s.name}
                <span
                  className={`rounded px-1.5 py-0.5 text-xs ${CATEGORY_COLORS[s.category] ?? "bg-gray-100"}`}
                >
                  {s.category === "new"
                    ? "To Do"
                    : s.category === "indeterminate"
                      ? "In Progress"
                      : "Done"}
                </span>
              </button>
            ))
          )}
        </div>
      )}
      {value &&
        !statuses.some((s) => s.name === value) &&
        !isLoading && (
          <p className="mt-1 text-xs text-amber-600" data-testid="status-warning">
            This status was not found in Jira. The step will be saved but may
            not function correctly.
          </p>
        )}
    </div>
  );
}
