interface BrokenStepBadgeProps {
  tooltip?: string;
}

export function BrokenStepBadge({
  tooltip = "Status not found in Jira",
}: BrokenStepBadgeProps) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700"
      title={tooltip}
      data-testid="broken-step-badge"
    >
      &#9888; Invalid status
    </span>
  );
}
