import { useState } from "react";
import { TemplateList } from "./TemplateList";
import { TemplateEditor } from "./TemplateEditor";
import { CycleTimeBoxPlot } from "./CycleTimeBoxPlot";
import { ApplyTemplatePanel } from "./ApplyTemplatePanel";
import { useTemplate } from "@/hooks/useTemplates";

export function TemplatePage() {
  const [activeTemplateId, setActiveTemplateId] = useState<number | null>(null);
  const { data: template } = useTemplate(activeTemplateId);

  return (
    <div className="space-y-6">
      <TemplateList activeTemplateId={activeTemplateId} onSelect={setActiveTemplateId} />

      {activeTemplateId && (
        <>
          <div className="border-t pt-6">
            <TemplateEditor templateId={activeTemplateId} />
          </div>

          {/* Cycle Time Box Plot */}
          {template && template.entries.length > 0 && (
            <div className="border-t pt-6">
              <CycleTimeBoxPlot
                entries={template.entries.map((e) => ({
                  issue_type: e.issue_type,
                  story_points: e.story_points,
                  ct_min: e.ct_min,
                  ct_q1: e.ct_q1,
                  ct_median: e.ct_median,
                  ct_q3: e.ct_q3,
                  ct_max: e.ct_max,
                }))}
              />
            </div>
          )}

          {/* Apply to teams */}
          <div className="border-t pt-6">
            <ApplyTemplatePanel templateId={activeTemplateId} />
          </div>
        </>
      )}
    </div>
  );
}
