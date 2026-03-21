import { useState } from "react";
import { TemplateList } from "./TemplateList";
import { TemplateEditor } from "./TemplateEditor";
import { ApplyTemplatePanel } from "./ApplyTemplatePanel";

export function TemplatePage() {
  const [activeTemplateId, setActiveTemplateId] = useState<number | null>(null);

  return (
    <div className="space-y-6">
      <TemplateList activeTemplateId={activeTemplateId} onSelect={setActiveTemplateId} />

      {activeTemplateId && (
        <>
          <div className="border-t pt-6">
            <TemplateEditor templateId={activeTemplateId} />
          </div>

          {/* Apply to teams */}
          <div className="border-t pt-6">
            <ApplyTemplatePanel templateId={activeTemplateId} />
          </div>
        </>
      )}
    </div>
  );
}
