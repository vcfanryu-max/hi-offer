"use client";

import type { DebugTrace, ValidationDebugError } from "@/lib/types";

const moduleName = {
  resume_structure: "Resume Structure",
  jd_analysis: "JD Analysis",
  match_analysis: "Match Analysis",
  hr_message: "HR Message",
  resume_advice: "Resume Advice",
};

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <section className="debug-block">
      <h4>{label}</h4>
      <pre>{value == null ? "—" : typeof value === "string" ? value : JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

function ErrorTable({ errors }: { errors: ValidationDebugError[] }) {
  if (!errors.length) return <p className="debug-empty">没有校验错误。</p>;
  return (
    <div className="debug-error-list">
      {errors.map((error, index) => (
        <dl key={`${error.field_path}-${error.error_code}-${index}`}>
          <div><dt>Field Path</dt><dd>{error.field_path}</dd></div>
          <div><dt>Error Code</dt><dd>{error.error_code}</dd></div>
          <div><dt>Expected</dt><dd>{error.expected}</dd></div>
          <div><dt>Received</dt><dd><code>{JSON.stringify(error.received)}</code></dd></div>
          <div><dt>Message</dt><dd>{error.validation_message}</dd></div>
        </dl>
      ))}
    </div>
  );
}

export function DebugPanel({ traces }: { traces: DebugTrace[] }) {
  if (!traces.length) return null;
  return (
    <details className="debug-panel">
      <summary>
        <span>Development Debug Trace</span>
        <span>{traces.length} MODULE TRACE{traces.length > 1 ? "S" : ""}</span>
      </summary>
      <div className="debug-panel-content">
        <p className="debug-privacy">仅开发模式可见。API Key、Authorization Header、Credential 与 Secret 永不写入此面板。</p>
        {traces.map((trace, index) => (
          <details className="debug-trace" key={`${trace.request_id}-${index}`} open={trace.validation_result === "invalid_after_repair"}>
            <summary>
              <strong>{moduleName[trace.module]}</strong>
              <span>{trace.validation_result}</span>
            </summary>
            <div className="debug-trace-body">
              <dl className="debug-meta">
                <div><dt>Module</dt><dd>{trace.module}</dd></div>
                <div><dt>Prompt Version</dt><dd>{trace.prompt_version}</dd></div>
                <div><dt>Provider</dt><dd>{trace.provider}</dd></div>
                <div><dt>Model</dt><dd>{trace.model}</dd></div>
                <div><dt>Request ID</dt><dd>{trace.request_id}</dd></div>
                <div><dt>Generation ID</dt><dd>{trace.generation_id ?? "—"}</dd></div>
                <div><dt>Repair</dt><dd>{trace.repair_attempted ? "attempted" : "not needed"}</dd></div>
                <div><dt>Repair Prompt</dt><dd>{trace.repair_prompt_version ?? "—"}</dd></div>
              </dl>
              <JsonBlock label="Raw LLM Output" value={trace.raw_output} />
              <JsonBlock label="Parsed JSON" value={trace.parsed_json} />
              <JsonBlock label="Normalized JSON" value={trace.normalized_json} />
              <JsonBlock label="Diagnostics / OCR / Long JD" value={trace.diagnostics} />
              <section className="debug-block"><h4>Pydantic Validation Errors</h4><ErrorTable errors={trace.validation_errors} /></section>
              {trace.repair_attempted && (
                <>
                  <JsonBlock label="Repair Raw Output" value={trace.repair_raw_output} />
                  <JsonBlock label="Repair Parsed JSON" value={trace.repair_parsed_json} />
                  <JsonBlock label="Repair Normalized JSON" value={trace.repair_normalized_json} />
                  <section className="debug-block"><h4>Repair Validation Errors</h4><ErrorTable errors={trace.repair_validation_errors} /></section>
                </>
              )}
            </div>
          </details>
        ))}
      </div>
    </details>
  );
}
