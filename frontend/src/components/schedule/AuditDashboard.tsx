import { useAuditSummary } from "@/hooks/useScheduledEvents";

interface AuditDashboardProps {
  teamId: number;
  sprintId: number;
}

const CARD_STYLES: Record<string, string> = {
  total: "bg-slate-50 text-slate-800",
  pending: "bg-yellow-50 text-yellow-800",
  dispatched: "bg-blue-50 text-blue-800",
  verified: "bg-green-50 text-green-800",
  failed: "bg-red-50 text-red-800",
  timeout: "bg-orange-50 text-orange-800",
};

export function AuditDashboard({ teamId, sprintId }: AuditDashboardProps) {
  const { data, isLoading } = useAuditSummary(teamId, sprintId);

  if (isLoading) {
    return <div className="py-4 text-sm text-muted-foreground">Loading audit data...</div>;
  }

  if (!data) {
    return null;
  }

  const cards = [
    { key: "total", label: "Total", value: data.total },
    { key: "pending", label: "Pending", value: data.pending },
    { key: "dispatched", label: "Dispatched", value: data.dispatched },
    { key: "verified", label: "Verified", value: data.verified },
    { key: "failed", label: "Failed", value: data.failed },
    { key: "timeout", label: "Timed Out", value: data.timeout },
  ];

  return (
    <div className="space-y-4 rounded-lg border bg-white p-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        Audit Summary
      </h3>

      {/* Summary cards */}
      <div className="grid grid-cols-6 gap-3">
        {cards.map(({ key, label, value }) => (
          <div
            key={key}
            className={`rounded-lg p-3 text-center ${CARD_STYLES[key]}`}
          >
            <div className="text-2xl font-bold tabular-nums">{value}</div>
            <div className="text-xs font-medium">{label}</div>
          </div>
        ))}
      </div>

      {/* Failures table */}
      {data.failures.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium text-red-700">Failures</h4>
          <div className="overflow-auto rounded-md border border-red-200">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-red-50">
                  <th className="px-3 py-1.5 text-left font-medium">Event ID</th>
                  <th className="px-3 py-1.5 text-left font-medium">Status</th>
                  <th className="px-3 py-1.5 text-left font-medium">Reason</th>
                  <th className="px-3 py-1.5 text-left font-medium">Verified At</th>
                  <th className="px-3 py-1.5 text-left font-medium">Alert</th>
                </tr>
              </thead>
              <tbody>
                {data.failures.map((f) => (
                  <tr key={f.id} className="border-b">
                    <td className="px-3 py-1.5 tabular-nums">{f.scheduled_event_id}</td>
                    <td className="px-3 py-1.5 font-medium">{f.verification_status}</td>
                    <td className="px-3 py-1.5">{f.failure_reason ?? "—"}</td>
                    <td className="px-3 py-1.5 tabular-nums">
                      {f.verified_at ? new Date(f.verified_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-3 py-1.5">{f.alert_sent ? "Sent" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
