import React from "react";
import { useEffect, useState } from "react";
import { getFieldPlaceholder } from "../utils/placeholder";

export default function FieldEditor({
  field,
  value,
  onChange,
  onConfirm,
  suggestion,
  onAccept,
  onDismiss,
  pending,
}) {
  const [draft, setDraft] = useState(value || "");

  useEffect(() => {
    setDraft(value || "");
  }, [value]);

  const label = String(field || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());

  return (
    <div className="field-card">
      <label htmlFor={field}>{label}</label>
      <textarea
        id={field}
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          onChange(field, e.target.value);
        }}
        onBlur={() => onChange(field, draft, true)}
        placeholder={getFieldPlaceholder(field)}
      />
      {onConfirm && (
        <div className="confirm-row">
          <button className="btn btn-secondary btn-sm" onClick={() => onConfirm(field, draft)}>
            Confirm response
          </button>
        </div>
      )}
      {pending && <p className="hint">Suggestion pending...</p>}
      {suggestion && (
        <div className="suggestion-inline suggestion-inline-ai">
          <p>{suggestion.suggested_text}</p>
          <div className="row gap-8">
            <button
              className="btn btn-sm btn-success"
              onClick={() => onAccept(field, suggestion.suggested_text)}
            >
              ✓
            </button>
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => onDismiss(field)}
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
