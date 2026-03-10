import React from "react";
import { useEffect, useState } from "react";
import { getFieldLabel, getFieldPlaceholder } from "../utils/placeholder";

export default function FieldEditor({
  field,
  value,
  onChange,
  onConfirm,
  suggestion,
  onAccept,
  onDismiss,
  pending,
  readOnly,
  labelOverride,
  placeholderOverride,
}) {
  const [draft, setDraft] = useState(value || "");
  const [hasInteracted, setHasInteracted] = useState(Boolean((value || "").trim().length));

  useEffect(() => {
    setDraft(value || "");
    if ((value || "").trim().length > 0) {
      setHasInteracted(true);
    }
  }, [value]);

  const label = labelOverride || getFieldLabel(field);
  const placeholder =
    hasInteracted ? "" : (placeholderOverride ?? getFieldPlaceholder(field));

  return (
    <div className="field-card">
      <label htmlFor={field}>{label}</label>
      <textarea
        id={field}
        value={draft}
        readOnly={readOnly}
        onChange={(e) => {
          if (readOnly) return;
          if (typeof onChange !== "function") return;
          setHasInteracted(true);
          setDraft(e.target.value);
          onChange(field, e.target.value);
        }}
        onBlur={() => {
          if (readOnly) return;
          if (typeof onChange !== "function") return;
          onChange(field, draft, true);
        }}
        placeholder={placeholder}
      />
      {onConfirm && (
        <div className="confirm-row">
          <button className="btn btn-secondary btn-sm" onClick={() => onConfirm(field, draft)}>
            Confirm response
          </button>
        </div>
      )}
      {pending && <p className="hint">Suggestion pending...</p>}
      {!readOnly && suggestion && (
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
