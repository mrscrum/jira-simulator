import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import type { DysfunctionMeta } from "@/lib/dysfunctions";
import type { DysfunctionConfig, DysfunctionConfigUpdate } from "@/lib/types";

interface DysfunctionModalProps {
  open: boolean;
  onClose: () => void;
  meta: DysfunctionMeta;
  config: DysfunctionConfig;
  onSave: (data: DysfunctionConfigUpdate) => void;
}

export function DysfunctionModal({
  open,
  onClose,
  meta,
  config,
  onSave,
}: DysfunctionModalProps) {
  const [values, setValues] = useState<Record<string, number>>(() => {
    const init: Record<string, number> = {};
    init[meta.probabilityField] =
      config[meta.probabilityField as keyof DysfunctionConfig] as number;
    for (const field of meta.modalFields) {
      init[field.key] = config[field.key as keyof DysfunctionConfig] as number;
    }
    return init;
  });

  const handleSave = () => {
    onSave(values as DysfunctionConfigUpdate);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{meta.name}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Probability */}
          <div className="space-y-2">
            <Label>Probability</Label>
            <Input
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={values[meta.probabilityField] ?? 0}
              onChange={(e) =>
                setValues((prev) => ({
                  ...prev,
                  [meta.probabilityField]: parseFloat(e.target.value) || 0,
                }))
              }
              data-testid="modal-probability"
            />
          </div>

          {/* Per-type fields */}
          {meta.modalFields.map((field) => (
            <div key={field.key} className="space-y-2">
              <Label>{field.label}</Label>
              <Input
                type="number"
                step="0.1"
                value={values[field.key] ?? 0}
                onChange={(e) =>
                  setValues((prev) => ({
                    ...prev,
                    [field.key]: parseFloat(e.target.value) || 0,
                  }))
                }
                data-testid={`field-${field.key}`}
              />
            </div>
          ))}
        </div>

        <Separator />

        {/* Compound effects - locked */}
        <div
          className="pointer-events-none opacity-45"
          data-testid="compound-section"
        >
          <h3 className="mb-2 font-medium">Compound effects</h3>
          <p className="text-sm text-muted-foreground">
            Configure how this dysfunction interacts with others when triggered
            simultaneously. Available in a future update.
          </p>
          <div className="mt-3 space-y-2">
            <div className="h-8 rounded bg-muted" />
            <div className="h-8 rounded bg-muted" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} data-testid="save-dysfunction-btn">
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
