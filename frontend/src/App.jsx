import { useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    if (!text.trim()) {
      alert("Please enter a prescription.");
      return;
    }

    setLoading(true);

    try {
      const res = await axios.post("http://127.0.0.1:8000/analyze", {
        text,
      });

      setResult(res.data);
    } catch (err) {
      alert("Backend not running!");
      console.error(err);
    }

    setLoading(false);
  };

  return (
    <div className="container">
      <div className="header">
        <h1>💊 Polypharmacy AI</h1>

        <p>
          AI-powered Drug Interaction Detection with Doctor & Patient
          Explanations
        </p>
      </div>

      <textarea
        rows="8"
        placeholder={`Example:

Digoxin 0.25 mg
Sympathomimetics
Take twice daily`}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      <button onClick={analyze}>
        {loading ? "Analyzing..." : "Analyze"}
      </button>

      {result && (
        <div className="result">
          <h2>Detected Drugs</h2>

          {result.drugs.length > 0 ? (
            <ul className="drug-list">
              {result.drugs.map((drug, index) => (
                <li key={index}>{drug}</li>
              ))}
            </ul>
          ) : (
            <p>No drugs detected.</p>
          )}

          <h2>Interactions</h2>

          {result.interactions.length > 0 ? (
            result.interactions.map((item, i) => (
              <div className="card" key={i}>
                <h3>
                  💊 {item.drug1} + {item.drug2}
                </h3>

                <p className="relation">
                  <b>Interaction Type:</b> {item.relation}
                </p>

                <p>{item.sentence}</p>
              </div>
            ))
          ) : (
            <p>No interactions found.</p>
          )}

          <h2>Doctor Explanation</h2>

          <pre>{result.doctor}</pre>

          <h2>Patient Explanation</h2>

          <pre>{result.patient}</pre>
        </div>
      )}
    </div>
  );
}

export default App;