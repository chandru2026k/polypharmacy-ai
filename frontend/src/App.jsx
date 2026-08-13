import { useState } from "react";
import axios from "axios";
import "./App.css";

const API_URL_MANUAL = "http://127.0.0.1:8000/check-interactions";
const API_URL_EXTRACT = "http://127.0.0.1:8000/extract-and-check";
const API_URL_OCR = "http://127.0.0.1:8000/ocr-and-check";

const SEVERITY_STYLES = {
  High: { bg: "#fde2e2", border: "#e05252", text: "#8a1f1f" },
  Moderate: { bg: "#fff3d6", border: "#e0a852", text: "#8a5a1f" },
  Low: { bg: "#e6f4ea", border: "#4caf6e", text: "#1f6b34" },
};

function severityStyle(severity) {
  return SEVERITY_STYLES[severity] || { bg: "#eee", border: "#999", text: "#333" };
}

function ConfidenceBadge({ confidence }) {
  const label =
    confidence === "exact"
      ? "Direct match"
      : confidence === "class_fallback"
      ? "Class-level match (lower confidence)"
      : "No match";
  const color =
    confidence === "exact" ? "#2f6f4f" : confidence === "class_fallback" ? "#8a6a1f" : "#888";
  return (
    <span
      style={{
        fontSize: "0.75rem",
        color,
        border: `1px solid ${color}`,
        borderRadius: "999px",
        padding: "2px 8px",
        marginLeft: "8px",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

function ExplanationToggle({ result }) {
  const [audience, setAudience] = useState("patient");
  const text =
    audience === "patient" ? result.patient_explanation : result.doctor_explanation;

  if (!result.doctor_explanation && !result.patient_explanation) return null;

  return (
    <div className="explanation-block">
      <div className="explanation-toggle">
        <button
          type="button"
          className={audience === "patient" ? "toggle-btn toggle-btn--active" : "toggle-btn"}
          onClick={() => setAudience("patient")}
        >
          For Patients
        </button>
        <button
          type="button"
          className={audience === "doctor" ? "toggle-btn toggle-btn--active" : "toggle-btn"}
          onClick={() => setAudience("doctor")}
        >
          For Doctors
        </button>
      </div>
      <p className="explanation-text">{text}</p>
    </div>
  );
}

function ResultCard({ result }) {
  const style = result.found ? severityStyle(result.severity) : null;

  if (!result.found) {
    return (
      <div className="result-card result-card--empty">
        <div className="result-card__header">
          <strong>{result.drug_1}</strong> + <strong>{result.drug_2}</strong>
          <ConfidenceBadge confidence={result.confidence} />
        </div>
        <p className="result-card__note">
          No known interaction found in our database. This does not guarantee the
          combination is safe — it may simply be absent from our source data.
        </p>
      </div>
    );
  }

  return (
    <div
      className="result-card"
      style={{ backgroundColor: style.bg, borderColor: style.border }}
    >
      <div className="result-card__header">
        <strong>{result.drug_1}</strong> + <strong>{result.drug_2}</strong>
        <ConfidenceBadge confidence={result.confidence} />
      </div>

      <div className="result-card__meta">
        <span
          className="severity-pill"
          style={{ backgroundColor: style.border, color: "white" }}
        >
          {result.severity} severity
        </span>
        <span className="relation-type">{result.relation_type}</span>
        <span className="mention-count">
          seen {result.mention_count} time{result.mention_count === 1 ? "" : "s"} in source data
        </span>
      </div>

      {result.evidence_sentence && (
        <p className="evidence" style={{ color: style.text }}>
          “{result.evidence_sentence}”
        </p>
      )}

      <ExplanationToggle result={result} />

      {result.note && <p className="result-card__note">{result.note}</p>}

      <div className="normalized-info">
        <span>
          {result.drug_1} → {result.drug_1_normalized.normalized}
          {result.drug_1_normalized.match_type !== "assumed_generic" &&
            ` (${result.drug_1_normalized.match_type})`}
        </span>
        <span>
          {result.drug_2} → {result.drug_2_normalized.normalized}
          {result.drug_2_normalized.match_type !== "assumed_generic" &&
            ` (${result.drug_2_normalized.match_type})`}
        </span>
      </div>
    </div>
  );
}

export default function App() {
  const [mode, setMode] = useState("manual"); // "manual" | "note" | "image"
  const [drugsInput, setDrugsInput] = useState("");
  const [noteInput, setNoteInput] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResponse(null);

    setLoading(true);
    try {
      let res;
      if (mode === "manual") {
        const drugs = drugsInput
          .split(",")
          .map((d) => d.trim())
          .filter(Boolean);

        if (drugs.length < 2) {
          setError("Enter at least 2 drug names, separated by commas.");
          setLoading(false);
          return;
        }
        res = await axios.post(API_URL_MANUAL, { drugs });
      } else if (mode === "note") {
        if (!noteInput.trim()) {
          setError("Paste some text containing drug names first.");
          setLoading(false);
          return;
        }
        res = await axios.post(API_URL_EXTRACT, { text: noteInput });
      } else {
        if (!imageFile) {
          setError("Choose an image of a prescription or medication list first.");
          setLoading(false);
          return;
        }
        const formData = new FormData();
        formData.append("file", imageFile);
        res = await axios.post(API_URL_OCR, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
      }
      setResponse(res.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Could not reach the interaction checker API. Is the backend running?"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app__header">
        <h1>Polypharmacy Interaction Checker</h1>
        <p className="app__subtitle">
          Enter medications (brand or generic names) to check for known drug-drug
          interactions.
        </p>
      </header>

      <div className="mode-toggle">
        <button
          type="button"
          className={mode === "manual" ? "toggle-btn toggle-btn--active" : "toggle-btn"}
          onClick={() => setMode("manual")}
        >
          Manual List
        </button>
        <button
          type="button"
          className={mode === "note" ? "toggle-btn toggle-btn--active" : "toggle-btn"}
          onClick={() => setMode("note")}
        >
          Paste a Note
        </button>
        <button
          type="button"
          className={mode === "image" ? "toggle-btn toggle-btn--active" : "toggle-btn"}
          onClick={() => setMode("image")}
        >
          Upload a Photo
        </button>
      </div>

      <form
        className={mode === "manual" ? "input-form" : "input-form input-form--note"}
        onSubmit={handleSubmit}
      >
        {mode === "manual" ? (
          <input
            type="text"
            value={drugsInput}
            onChange={(e) => setDrugsInput(e.target.value)}
            placeholder="e.g. EQUETRO, ethosuximide, digoxin"
          />
        ) : mode === "note" ? (
          <textarea
            value={noteInput}
            onChange={(e) => setNoteInput(e.target.value)}
            placeholder="Paste a clinical note or medication list, e.g. 'Patient is on EQUETRO 200mg and ethosuximide 500mg for seizure control...'"
            rows={5}
          />
        ) : (
          <div className="image-upload">
            <input
              type="file"
              accept="image/png, image/jpeg, image/webp"
              onChange={(e) => {
                const file = e.target.files?.[0] || null;
                setImageFile(file);
                setImagePreviewUrl(file ? URL.createObjectURL(file) : null);
              }}
            />
            {imagePreviewUrl && (
              <img src={imagePreviewUrl} alt="Selected prescription" className="image-preview" />
            )}
          </div>
        )}
        <button type="submit" disabled={loading}>
          {loading ? "Checking..." : "Check Interactions"}
        </button>
      </form>

      {error && <div className="error-banner">{error}</div>}

      {response && (
        <div className="results">
          <div className="results__summary">
            Checked {response.pairs_checked} pair
            {response.pairs_checked === 1 ? "" : "s"} across {response.drug_count}{" "}
            medications — <strong>{response.interactions_found}</strong> interaction
            {response.interactions_found === 1 ? "" : "s"} found.
          </div>
          {response.results.map((result, idx) => (
            <ResultCard key={idx} result={result} />
          ))}
        </div>
      )}
    </div>
  );
}