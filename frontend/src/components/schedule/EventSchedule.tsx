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
  useSuggestedStart,
  useCreateSprint,
  useCreateSprintBatch,
  useUpdateSprint,
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

function formatDateForInput(iso: string | undefined | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  // Format as YYYY-MM-DDTHH:mm for datetime-local input
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function EventSchedule({ teamId }: EventScheduleProps) {
  const [sprintId, setSprintId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [selectedEvent, setSelectedEvent] = useState<ScheduledEvent | null>(null);
  const [activeTab, setActiveTab] = useState<TabView>("items");
  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [createMode, setCreateMode] = useState<"single" | "batch">("single");

  // Single sprint create form
  const [createStartDate, setCreateStartDate] = useState("");
  const [createEndDate, setCreateEndDate] = useState("");
  const [createSimulate, setCreateSimulate] = useState(true);

  // Batch create form
  const [batchStartDate, setBatchStartDate] = useState("");
  const [batchCount, setBatchCount] = useState(3);

  // Edit sprint form
  const [showEditPanel, setShowEditPanel] = useState(false);
  const [editName, setEditName] = useState("");
  const [editStartDate, setEditStartDate] = useState("");
  const [editEndDate, setEditEndDate] = useState("");
  const [editGoal, setEditGoal] = useState("");

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
  const { data: suggestion } = useSuggestedStart(teamId);
  const createSprint = useCreateSprint();
  const createBatch = useCreateSprintBatch();
  const updateSprint = useUpdateSprint();

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

  const canEdit = selectedSprint && (selectedSprint.phase === "PLANNING" || selectedSprint.phase === "SIMULATED");

  function openEditPanel() {
    if (!selectedSprint) return;
    setEditName(selectedSprint.name);
    setEditStartDate(formatDateForInput(selectedSprint.start_date));
    setEditEndDate(formatDateForInput(selectedSprint.end_date));
    setEditGoal("");
    setShowEditPanel(true);
  }

  function handleCreateSingle() {
    const startDate = createStartDate || (suggestion?.suggested_start ?? null);
    const endDate = createEndDate || null;
    createSprint.mutate(
      {
        teamId,
        data: {
          start_date: startDate,
          end_date: endDate,
          simulate: createSimulate,
        },
      },
      {
        onSuccess: (result: Record<string, unknown>) => {
          if (result.sprint_id) {
            setSprintId(result.sprint_id as number);
          }
          setShowCreatePanel(false);
        },
      },
    );
  }

  function handleCreateBatch() {
    const startDate = batchStartDate || (suggestion?.suggested_start ?? null);
    createBatch.mutate(
      {
        teamId,
        data: {
          start_date: startDate,
          count: batchCount,
          simulate: false,
        },
      },
      {
        onSuccess: () => {
          setShowCreatePanel(false);
        },
      },
    );
  }

  function handleEditSave() {
    if (!sprintId) return;
    updateSprint.mutate(
      {
        teamId,
        sprintId,
        data: {
          start_date: editStartDate ? new Date(editStartDate).toISOString() : null,
          end_date: editEndDate ? new Date(editEndDate).toISOString() : null,
          name: editName || null,
          goal: editGoal || null,
        },
      },
      { onSuccess: () => setShowEditPanel(false) },
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <h2 className="text-xl font-semibold">Event Schedule</h2>

      {/* Sprint Actions */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 p-4">
        <span className="text-sm font-medium text-muted-foreground mr-1">Actions:</span>

        {/* Create Sprint */}
        <button
          onClick={() => {
            // Pre-fill dates from suggestion
            if (suggestion) {
              setCreateStartDate(formatDateForInput(suggestion.suggested_start));
              setCreateEndDate(formatDateForInput(suggestion.suggested_end));
              setBatchStartDate(formatDateForInput(suggestion.suggested_start));
            }
            setShowCreatePanel(!showCreatePanel);
          }}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          Create Sprint
        </button>

        {/* Activate Sprint */}
        {sprintId && selectedSprint?.phase === "SIMULATED" && (
          <button
            onClick={() => activate.mutate({ teamId, sprintId })}
            disabled={activate.isPending}
            className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-50"
          >
            {activate.isPending ? "Activating..." : "Activate Sprint"}
          </button>
        )}

        {/* Re-simulate */}
        {sprintId && selectedSprint?.phase === "SIMULATED" && (
          <button
            onClick={() => recompute.mutate({ teamId, sprintId })}
            disabled={recompute.isPending}
            className="rounded-md bg-amber-600 px-3 py-1.5 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {recompute.isPending ? "Re-simulating..." : "Re-simulate"}
          </button>
        )}

        {/* Edit Sprint */}
        {sprintId && canEdit && (
          <button
            onClick={openEditPanel}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Edit Sprint
          </button>
        )}

        {/* Delete Sprint */}
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
                  { onSuccess: () => setSprintId(null) },
                );
              }
            }}
            disabled={deleteSpr.isPending}
            className="rounded-md bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50"
          >
            {deleteSpr.isPending ? "Deleting..." : "Delete Sprint"}
          </button>
        )}

        {/* Manual dispatch */}
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

      {/* Create Sprint Panel */}
      {showCreatePanel && (
        <div className="rounded-lg border bg-white p-4 space-y-4 shadow-sm">
          <div className="flex items-center gap-2 border-b pb-2">
            <button
              onClick={() => setCreateMode("single")}
              className={`px-3 py-1 text-sm rounded-md ${createMode === "single" ? "bg-blue-100 text-blue-800 font-medium" : "text-muted-foreground hover:bg-accent"}`}
            >
              Single Sprint
            </button>
            <button
              onClick={() => setCreateMode("batch")}
              className={`px-3 py-1 text-sm rounded-md ${createMode === "batch" ? "bg-blue-100 text-blue-800 font-medium" : "text-muted-foreground hover:bg-accent"}`}
            >
              Batch Create
            </button>
            <div className="flex-1" />
            <button
              onClick={() => setShowCreatePanel(false)}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>

          {createMode === "single" ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Start Date</label>
                  <input
                    type="datetime-local"
                    value={createStartDate}
                    onChange={(e) => setCreateStartDate(e.target.value)}
                    className="w-full rounded-md border px-2 py-1.5 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">End Date (optional)</label>
                  <input
                    type="datetime-local"
                    value={createEndDate}
                    onChange={(e) => setCreateEndDate(e.target.value)}
                    className="w-full rounded-md border px-2 py-1.5 text-sm"
                  />
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Defaults to {suggestion?.sprint_length_days ?? "?"} working days
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={createSimulate}
                    onChange={(e) => setCreateSimulate(e.target.checked)}
                    className="rounded"
                  />
                  Simulate immediately
                </label>
                <button
                  onClick={handleCreateSingle}
                  disabled={createSprint.isPending}
                  className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {createSprint.isPending ? "Creating..." : "Create Sprint"}
                </button>
              </div>
              {suggestion && (
                <p className="text-xs text-muted-foreground">
                  Suggested: Sprint #{suggestion.sprint_number}, {new Date(suggestion.suggested_start).toLocaleDateString()} - {new Date(suggestion.suggested_end).toLocaleDateString()}
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Start Date</label>
                  <input
                    type="datetime-local"
                    value={batchStartDate}
                    onChange={(e) => setBatchStartDate(e.target.value)}
                    className="w-full rounded-md border px-2 py-1.5 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-muted-foreground mb-1">Number of Sprints</label>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={batchCount}
                    onChange={(e) => setBatchCount(Number(e.target.value))}
                    className="w-full rounded-md border px-2 py-1.5 text-sm"
                  />
                </div>
              </div>
              <div className="flex items-center gap-4">
                <button
                  onClick={handleCreateBatch}
                  disabled={createBatch.isPending}
                  className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {createBatch.isPending ? "Creating..." : `Create ${batchCount} Sprints`}
                </button>
              </div>
            </div>
          )}

          {/* Error messages */}
          {createSprint.isError && (
            <div className="rounded-md bg-red-50 p-2 text-sm text-red-800">
              {(createSprint.error as Error)?.message ?? "Failed to create sprint"}
            </div>
          )}
          {createBatch.isError && (
            <div className="rounded-md bg-red-50 p-2 text-sm text-red-800">
              {(createBatch.error as Error)?.message ?? "Failed to create sprints"}
            </div>
          )}
        </div>
      )}

      {/* Edit Sprint Panel */}
      {showEditPanel && selectedSprint && (
        <div className="rounded-lg border bg-white p-4 space-y-3 shadow-sm">
          <div className="flex items-center justify-between border-b pb-2">
            <span className="text-sm font-medium">Edit Sprint: {selectedSprint.name}</span>
            <button
              onClick={() => setShowEditPanel(false)}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Name</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full rounded-md border px-2 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Goal</label>
              <input
                type="text"
                value={editGoal}
                onChange={(e) => setEditGoal(e.target.value)}
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                placeholder="Sprint goal..."
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">Start Date</label>
              <input
                type="datetime-local"
                value={editStartDate}
                onChange={(e) => setEditStartDate(e.target.value)}
                className="w-full rounded-md border px-2 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1">End Date</label>
              <input
                type="datetime-local"
                value={editEndDate}
                onChange={(e) => setEditEndDate(e.target.value)}
                className="w-full rounded-md border px-2 py-1.5 text-sm"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleEditSave}
              disabled={updateSprint.isPending}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {updateSprint.isPending ? "Saving..." : "Save Changes"}
            </button>
            <span className="text-xs text-muted-foreground">
              Changing dates will clear existing simulation events. Re-simulate after saving.
            </span>
          </div>
          {updateSprint.isError && (
            <div className="rounded-md bg-red-50 p-2 text-sm text-red-800">
              {(updateSprint.error as Error)?.message ?? "Failed to update sprint"}
            </div>
          )}
          {updateSprint.isSuccess && (
            <div className="rounded-md bg-green-50 p-2 text-sm text-green-800">
              Sprint updated.
              <button onClick={() => { updateSprint.reset(); setShowEditPanel(false); }} className="ml-2 underline">
                Dismiss
              </button>
            </div>
          )}
        </div>
      )}

      {/* Feedback banners */}
      {createSprint.isSuccess && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Sprint created successfully.
          <button onClick={() => createSprint.reset()} className="ml-2 underline">
            Dismiss
          </button>
        </div>
      )}
      {createBatch.isSuccess && (
        <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
          Sprints created successfully.
          <button onClick={() => createBatch.reset()} className="ml-2 underline">
            Dismiss
          </button>
        </div>
      )}
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
            setShowEditPanel(false);
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

        {/* Date range display */}
        {selectedSprint?.start_date && selectedSprint?.end_date && (
          <span className="text-xs text-muted-foreground">
            {new Date(selectedSprint.start_date).toLocaleDateString()} — {new Date(selectedSprint.end_date).toLocaleDateString()}
          </span>
        )}

        {/* Cancel all pending */}
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
          Select a sprint or create a new one to see events
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
