import { useState } from "react";
import { useSprintItems, useItemEvents } from "@/hooks/useScheduledEvents";

const TYPE_COLORS: Record<string, string> = {
  Story: "bg-green-100 text-green-800",
  Bug: "bg-red-100 text-red-800",
  Task: "bg-blue-100 text-blue-800",
  Spike: "bg-purple-100 text-purple-800",
  Enabler: "bg-orange-100 text-orange-800",
};

interface SprintItemListProps {
  teamId: number;
  sprintId: number;
}

export function SprintItemList({ teamId, sprintId }: SprintItemListProps) {
  const { data: items, isLoading } = useSprintItems(teamId, sprintId);
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null);

  if (isLoading) {
    return <div className="py-8 text-center text-muted-foreground">Loading items...</div>;
  }

  if (!items || items.length === 0) {
    return <div className="py-8 text-center text-muted-foreground">No items in this sprint</div>;
  }

  return (
    <div className="overflow-auto rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium w-8"></th>
            <th className="px-3 py-2 text-left font-medium">Key</th>
            <th className="px-3 py-2 text-left font-medium">Summary</th>
            <th className="px-3 py-2 text-left font-medium">Type</th>
            <th className="px-3 py-2 text-left font-medium">SP</th>
            <th className="px-3 py-2 text-left font-medium">Status</th>
            <th className="px-3 py-2 text-left font-medium">Events</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <>
              <tr
                key={item.id}
                className="border-b hover:bg-muted/30 cursor-pointer"
                onClick={() => setExpandedItemId(expandedItemId === item.id ? null : item.id)}
              >
                <td className="px-3 py-2 text-muted-foreground">
                  {expandedItemId === item.id ? "\u25BC" : "\u25B6"}
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {item.jira_issue_key ?? `#${item.id}`}
                </td>
                <td className="px-3 py-2 max-w-md truncate">{item.summary}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[item.issue_type] ?? "bg-gray-100"}`}>
                    {item.issue_type}
                  </span>
                </td>
                <td className="px-3 py-2 tabular-nums">{item.story_points ?? "\u2014"}</td>
                <td className="px-3 py-2">{item.status}</td>
                <td className="px-3 py-2 tabular-nums">{item.event_count}</td>
              </tr>
              {expandedItemId === item.id && (
                <tr key={`${item.id}-events`}>
                  <td colSpan={7} className="px-6 py-3 bg-muted/20">
                    <ItemEventTimeline teamId={teamId} sprintId={sprintId} issueId={item.id} />
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ItemEventTimeline({
  teamId,
  sprintId,
  issueId,
}: {
  teamId: number;
  sprintId: number;
  issueId: number;
}) {
  const { data: events, isLoading } = useItemEvents(teamId, sprintId, issueId);

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading events...</div>;
  if (!events || events.length === 0) return <div className="text-sm text-muted-foreground">No events</div>;

  return (
    <div className="space-y-1">
      <div className="text-xs font-medium text-muted-foreground mb-2">
        {events.length} event{events.length !== 1 ? "s" : ""} scheduled
      </div>
      {events.map((ev) => (
        <div key={ev.id} className="flex items-center gap-3 text-xs">
          <span className="tabular-nums text-muted-foreground w-16">
            Tick {ev.sim_tick}
          </span>
          <span className="tabular-nums text-muted-foreground w-36">
            {new Date(ev.scheduled_at).toLocaleString()}
          </span>
          <span className="font-mono bg-muted px-1.5 py-0.5 rounded">
            {ev.event_type}
          </span>
          {ev.payload?.target_status != null && (
            <span className="text-muted-foreground">
              &rarr; {String(ev.payload.target_status)}
            </span>
          )}
          <span className={`rounded-full px-2 py-0.5 text-xs ${
            ev.status === "DISPATCHED" ? "bg-green-100 text-green-800" :
            ev.status === "PENDING" ? "bg-yellow-100 text-yellow-800" :
            "bg-gray-100"
          }`}>
            {ev.status}
          </span>
        </div>
      ))}
    </div>
  );
}
