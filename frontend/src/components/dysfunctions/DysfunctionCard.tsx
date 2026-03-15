import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import type { DysfunctionMeta } from "@/lib/dysfunctions";
import type { DysfunctionConfig } from "@/lib/types";

interface DysfunctionCardProps {
  meta: DysfunctionMeta;
  config: DysfunctionConfig;
  onProbabilityChange: (value: number) => void;
  onToggle: (enabled: boolean) => void;
  onEdit: () => void;
}

export function DysfunctionCard({
  meta,
  config,
  onProbabilityChange,
  onToggle,
  onEdit,
}: DysfunctionCardProps) {
  const probability =
    (config[meta.probabilityField as keyof DysfunctionConfig] as number) ?? 0;
  const enabled = probability > 0;

  return (
    <div
      className="rounded-lg border bg-card p-4"
      data-testid={`dysfunction-card-${meta.type}`}
    >
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="font-medium">{meta.name}</h3>
          <p className="text-sm text-muted-foreground">{meta.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            checked={enabled}
            onCheckedChange={onToggle}
            data-testid={`toggle-${meta.type}`}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={onEdit}
            data-testid={`edit-${meta.type}`}
          >
            Edit
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Slider
          value={[Math.round(probability * 100)]}
          onValueChange={(val) => {
            const v = Array.isArray(val) ? val[0] : val;
            onProbabilityChange(v / 100);
          }}
          max={100}
          step={1}
          className="flex-1"
          data-testid={`slider-${meta.type}`}
        />
        <span className="w-12 text-right text-sm font-medium" data-testid={`probability-${meta.type}`}>
          {Math.round(probability * 100)}%
        </span>
      </div>
    </div>
  );
}
