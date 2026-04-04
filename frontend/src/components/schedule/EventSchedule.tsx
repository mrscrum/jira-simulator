import { useState } from "react";
import type { ScheduledEvent, SprintSummary } from "@/lib/types";
import {
  useTeamSprints,
  useScheduledEvents,
  useCancelEvent,
  useCancelAllEvents,
  usePrecompute,
  useRecompute,
  useActivateSprint,
  useDeleteSprint,
  useManualDispatch,
} from "@/hooks/useScheduledEvents";
import { EventDetail } from "./EventDetail";
import { AuditDashboard } from "./AuditDashboard";
import { SprintItemList } from "./SprintItemList";
import { FlowMatrix } from "./FlowMatrix";

const STATUS_COLORS: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  MODIFIED: "bg-blue-100 text-blue-800",
  DISPATCHED: "bg-green-100 text-green-800",
  FAILED: "bg-red-100 text-red-800",
  SKIPPED: "bg-gray-100 text-gray-500",
};

const PHASE_COLORS: Record<string, string> = {
  PLANNING: "bg-gray-100 text-gray-700",
  SIMULATED: "bg-purple-100 text-purple-800",
  ACTIVE: "bg-green-100 text-green-800",
  COMPLETED: "bg-blue-100 text-blue-800",
};

type TabView = "items" | "timeline" | "flow" | "audit";

interface EventScheduleProps {
  teamId: number;
}

export function EventSchedule({ teamId }: EventScheduleProps) {
  const [sprintId, setSprintId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [selectedEvent, setSelectedEvent] = useState<ScheduledEvent | null>(null);
  const [activeTab, setActiveTab] = useState<TabView>("items");

  const { data: sprints } = useTeamSprints(teamId);
  const { data, isLoading } = useScheduledEvents(teamId, sprintId, {
    status: statusFilter,
    page,
    page_size: 50,
  });
  const cancelEvent = useCancelEvent();
  const cancelAll = useCancelAllEvents();
  const precompute = usePrecompute();
  const recompute = useRecompute();
  const activate = useActivateSprint();
  const deleteSpr = useDeleteSprint();
  const dispatch = useManualDispatch();

  const events = data?.events ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 50);

  const selectedSprint: SprintSummary | undefined = (sprints ?? []).find(
    (s) => s.id === sprintId,
  );

  const tabs: { key: TabView; label: string }[] = [
    { key: "items", label: "Sprint Items" },
    { key: "flow", label: "Flow Matrix" },
    { key: "timeline", label: "Event Timeline" },
    { key: "audit", label: "Audit" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <h2 className="text-xl font-semibold">Event Schedule</h2>

      {/* Sprint Actions — clear lifecycle separation */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 p-4">
        <span className="text-sm font-medium text-muted-foreground mr-1">Actions:</span>

        {/* 1. Create & Simulate Sprint */}
        <button
          onClick={() => precompute.mutate({ teamId })}
          disabled={precompute.isPending}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {precompute.isPending ? "Computing..." : "Create & Simulate Sprint"}
        </button>

        {/* 2. Activate Sprint (only for SIMULATED sprints) */}
        {sprintId && selectedSprint?.phase === "SIMULATED" && (
          <button
            onClick={() => activate.mutate({ teamId, sprintId })}
            disabled={activate.isPending}
            className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-50"
          >
            {activate.isPending ? "Activating..." : "Activate Sprint"}
          </button>
        )}

        {/* 3. Re-simulate (only for SIMULATED sprints — re-run simulation) */}
        {sprintId && selectedSprint?.phase === "SIMULATED" && (
          <button
            onClick={() => recompute.mutate({ teamId, sprintId })}
            disabled={recompute.isPending}
            className="rounded-md bg-amber-600 px-3 py-1.5 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {recompute.isPending ? "Re-simulating..." : "Re-simulate"}
          </button>
        )}

        {/* 4. Delete Sprint */}
        {sprintId && selectedSprint && (
            <button
              onClick={() => {
                if (
                  confirm(
                    `Delete sprint "${selectedSprint.name}" and all its events? This cannot be undone.`,
                  )
                ) {
                  deleteSpr.mutate(
                    { teamId, sprintId },
                    {
                      onSuccess: () => setSprintId(null),
                    },
                  );
                }
              }}
              disabled={deleteSpr.isPending}
              className="rounded-md bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50"
            >
              {deleteSpr.isPending ? "Deleting..." : "Delete Sprint"}
            </button>
          )}

        {/* Manual dispatch (for ACTIVE sprints) */}
        {sprintId && selectedSprint?.phase === "ACTIVE" && (
          <button
            onClick={() => dispatch.mutate()}
            disabled={dispatch.isPending}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
          >
            {dispatch.isPending ? "Dispatching..." : "Manual Dispatch"}
          </button>
        )}
      </div>

      {/* Feedback banners */}
      {precompute.isSuccess && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Sprint pre-computed: {precompute.data.total_events} events across{" "}
          {precompute.data.total_ticks} ticks (batch: {precompute.data.batch_id.slice(0, 8)}...)
          <button
            onClick={() => {
              setSprintId(precompute.data.sprint_id);
              precompute.reset();
            }}
            className="ml-2 underline"
          >
            View events
          </button>
        </div>
      )}
      {precompute.isError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          Pre-compute failed: {(precompute.error as Error)?.message ?? "Unknown error"}
        </div>
      )}
      {activate.isSuccess && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Sprint activated! Events will be dispatched on schedule.
          <button onClick={() => activate.reset()} className="ml-2 underline">
            Dismiss
          </button>
        </div>
      )}
      {activate.isError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          Activation failed: {(activate.error as Error)?.message ?? "Unknown error"}
        </div>
      )}
      {deleteSpr.isSuccess && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Sprint deleted.
          <button onClick={() => deleteSpr.reset()} className="ml-2 underline">
            Dismiss
          </button>
        </div>
      )}
      {deleteSpr.isError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          Delete failed: {(deleteSpr.error as Error)?.message ?? "Unknown error"}
        </div>
      )}
      {recompute.isSuccess && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Re-simulation complete: {recompute.data.total_events} events across{" "}
          {recompute.data.total_ticks} ticks.
          <button onClick={() => recompute.reset()} className="ml-2 underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Sprint selector */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-muted-foreground">Sprint:</label>
        <select
          value={sprintId ?? ""}
          onChange={(e) => {
            const val = e.target.value ? parseInt(e.target.value, 10) : null;
            setSprintId(val);
            setPage(1);
          }}
          className="min-w-[320px] rounded-md border px-2 py-1 text-sm"
        >
          <option value="">Select a sprint...</option>
          {(sprints ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.phase}
              {s.committed_points != null ? ` \u2022 ${s.committed_points} pts` : ""})
            </option>
          ))}
        </select>

        {/* Phase badge */}
        {selectedSprint && (
          <span
            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
              PHASE_COLORS[selectedSprint.phase] ?? "bg-gray-100"
            }`}
          >
            {selectedSprint.phase}
          </span>
        )}

        {/* Cancel all pending (available for any sprint with events) */}
        {sprintId && selectedSprint?.phase !== "COMPLETED" && (
          <button
            onClick={() => {
              if (confirm("Cancel all pending events for this sprint?")) {
                cancelAll.mutate({ teamId, sprintId });
              }
            }}
            disabled={cancelAll.isPending}
            className="rounded-md border border-red-300 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Cancel All Pending
          </button>
        )}
      </div>

      {/* Tabs */}
      {sprintId && (
        <div className="flex gap-1 border-b">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                activeTab === tab.key
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Tab content */}
      {!sprintId ? (
        <div className="py-8 text-center text-muted-foreground">
          Select a sprint or create & simulate a new one to see events
        </div>
      ) : activeTab === "items" ? (
        <SprintItemList teamId={teamId} sprintId={sprintId} />
      ) : activeTab === "flow" ? (
        <FlowMatrix teamId={teamId} sprintId={sprintId} />
      ) : activeTab === "audit" ? (
        <AuditDashboard teamId={teamId} sprintId={sprintId} />
      ) : (
        /* Event Timeline tab */
        <>
          <div className="flex items-center gap-3">
            <select
              value={statusFilter ?? ""}
              onChange={(e) => {
                setStatusFilter(e.target.value || undefined);
                setPage(1);
              }}
              className="rounded-md border px-2 py-1 text-sm"
            >
              <option value="">All statuses</option>
              <option value="PENDING">Pending</option>
              <option value="MODIFIED">Modified</option>
              <option value="DISPATCHED">Dispatched</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </div>

          {isLoading ? (
            <div className="py-8 text-center text-muted-foreground">Loading events...</div>
          ) : events.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">No events found</div>
          ) : (
            <>
              <div className="overflow-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-3 py-2 text-left font-medium">Tick</th>
                      <th className="px-3 py-2 text-left font-medium">Scheduled At</th>
                      <th className="px-3 py-2 text-left font-medium">Type</th>
                      <th className="px-3 py-2 text-left font-medium">Issue</th>
                      <th className="px-3 py-2 text-left font-medium">Status</th>
                      <th className="px-3 py-2 text-left font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr key={event.id} className="border-b hover:bg-muted/30">
                        <td className="px-3 py-2 tabular-nums">{event.sim_tick}</td>
                        <td className="px-3 py-2 tabular-nums">
                          {new Date(event.scheduled_at).toLocaleString()}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs">{event.event_type}</td>
                        <td className="px-3 py-2">
                          {String(event.payload?.issue_key ?? event.issue_id ?? "\u2014")}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                              STATUS_COLORS[event.status] ?? "bg-gray-100"
                            }`}
                          >
                            {event.status}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            <button
                              onClick={() => setSelectedEvent(event)}
                              className="rounded px-2 py-0.5 text-xs hover:bg-accent"
                            >
                              View
                            </button>
                            {(event.status === "PENDING" || event.status === "MODIFIED") && (
                              <button
                                onClick={() => cancelEvent.mutate({ eventId: event.id })}
                                disabled={cancelEvent.isPending}
                                className="rounded px-2 py-0.5 text-xs text-red-600 hover:bg-red-50"
                              >
                                Cancel
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {totalPages > 1 && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{total} events total</span>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="rounded-md border px-2 py-1 text-sm disabled:opacity-50"
                    >
                      Prev
                    </button>
                    <span className="px-2 py-1 text-sm">
                      {page} / {totalPages}
                    </span>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                      className="rounded-md border px-2 py-1 text-sm disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Event detail modal */}
      {selectedEvent && (
        <EventDetail event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      )}
    </div>
  );
}
