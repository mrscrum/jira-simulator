import { useState } from "react";
import type { ScheduledEvent } from "@/lib/types";
import { useCancelEvent, useModifyEvent } from "@/hooks/useScheduledEvents";

interface EventDetailProps {
  event: ScheduledEvent;
  onClose: () => void;
}

export function EventDetail({ event, onClose }: EventDetailProps) {
  const [editMode, setEditMode] = useState(false);
  const [newTime, setNewTime] = useState(event.scheduled_at.slice(0, 16));
  const [newPayload, setNewPayload] = useState(
    JSON.stringify(event.payload, null, 2),
  );
  const [cancelReason, setCancelReason] = useState("");

  const cancelMutation = useCancelEvent();
  const modifyMutation = useModifyEvent();

  const isPending = event.status === "PENDING" || event.status === "MODIFIED";

  function handleSave() {
    let parsedPayload: Record<string, unknown> | undefined;
    try {
      parsedPayload = JSON.parse(newPayload);
    } catch {
      alert("Invalid JSON payload");
      return;
    }

    modifyMutation.mutate(
      {
        eventId: event.id,
        data: {
          scheduled_at: new Date(newTime).toISOString(),
          payload: parsedPayload,
        },
      },
      { onSuccess: () => onClose() },
    );
  }

  function handleCancel() {
    cancelMutation.mutate(
      { eventId: event.id, reason: cancelReason || undefined },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-lg bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">
            Event #{event.id} — {event.event_type}
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            X
          </button>
        </div>

        <div className="space-y-4">
          {/* Metadata */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-muted-foreground">Status:</span>{" "}
              <span className="font-medium">{event.status}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Tick:</span>{" "}
              <span className="font-mono">{event.sim_tick}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Scheduled:</span>{" "}
              {new Date(event.scheduled_at).toLocaleString()}
            </div>
            <div>
              <span className="text-muted-foreground">Issue:</span>{" "}
              {event.issue_id ?? "—"}
            </div>
            {event.dispatched_at && (
              <div>
                <span className="text-muted-foreground">Dispatched:</span>{" "}
                {new Date(event.dispatched_at).toLocaleString()}
              </div>
            )}
            {event.cancelled_at && (
              <div>
                <span className="text-muted-foreground">Cancelled:</span>{" "}
                {new Date(event.cancelled_at).toLocaleString()}
              </div>
            )}
            {event.cancel_reason && (
              <div className="col-span-2">
                <span className="text-muted-foreground">Cancel reason:</span>{" "}
                {event.cancel_reason}
              </div>
            )}
            {event.modified_at && (
              <div>
                <span className="text-muted-foreground">Modified:</span>{" "}
                {new Date(event.modified_at).toLocaleString()}
              </div>
            )}
            <div>
              <span className="text-muted-foreground">Batch:</span>{" "}
              <span className="font-mono text-xs">{event.batch_id.slice(0, 8)}...</span>
            </div>
          </div>

          {/* Payload */}
          {editMode ? (
            <div className="space-y-2">
              <label className="block text-sm font-medium">Scheduled Time</label>
              <input
                type="datetime-local"
                value={newTime}
                onChange={(e) => setNewTime(e.target.value)}
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              />
              <label className="block text-sm font-medium">Payload (JSON)</label>
              <textarea
                value={newPayload}
                onChange={(e) => setNewPayload(e.target.value)}
                rows={10}
                className="w-full rounded-md border px-3 py-1.5 font-mono text-xs"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSave}
                  disabled={modifyMutation.isPending}
                  className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {modifyMutation.isPending ? "Saving..." : "Save Changes"}
                </button>
                <button
                  onClick={() => setEditMode(false)}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
                >
                  Cancel Edit
                </button>
              </div>
            </div>
          ) : (
            <div>
              <h4 className="mb-1 text-sm font-medium">Payload</h4>
              <pre className="max-h-60 overflow-auto rounded-md bg-muted/50 p-3 text-xs">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </div>
          )}

          {/* Original values if modified */}
          {event.original_scheduled_at && (
            <div className="rounded-md bg-amber-50 p-3 text-sm">
              <strong>Original time:</strong>{" "}
              {new Date(event.original_scheduled_at).toLocaleString()}
            </div>
          )}
          {event.original_payload && (
            <div>
              <h4 className="mb-1 text-sm font-medium text-amber-700">Original Payload</h4>
              <pre className="max-h-40 overflow-auto rounded-md bg-amber-50 p-3 text-xs">
                {JSON.stringify(event.original_payload, null, 2)}
              </pre>
            </div>
          )}

          {/* Actions */}
          {isPending && !editMode && (
            <div className="flex gap-2 border-t pt-4">
              <button
                onClick={() => setEditMode(true)}
                className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
              >
                Edit
              </button>
              <div className="flex flex-1 gap-2">
                <input
                  type="text"
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="Cancel reason (optional)"
                  className="flex-1 rounded-md border px-3 py-1.5 text-sm"
                />
                <button
                  onClick={handleCancel}
                  disabled={cancelMutation.isPending}
                  className="rounded-md bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {cancelMutation.isPending ? "Cancelling..." : "Cancel Event"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
