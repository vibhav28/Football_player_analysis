import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getStatus } from "../api/client.js";

const STEP_ICON = { waiting: "…", running: "⟳", done: "✓", failed: "✗" };
const POLL_INTERVAL_MS = 2000;

// PRD section 40, Screen 3 — Processing
export default function ProcessingPage() {
  const { videoId } = useParams();
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    let timer;

    async function poll() {
      try {
        const status = await getStatus(videoId);
        if (cancelled) return;
        setJob(status);

        if (status.status === "Completed") {
          navigate(`/videos/${videoId}/analysis`);
          return;
        }
        if (status.status === "Failed") {
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [videoId, navigate]);

  return (
    <div className="page">
      <h2>Processing Video...</h2>

      {error && <p style={{ color: "#ff6b6b" }}>{error}</p>}

      {job?.status === "Failed" && (
        <div className="panel" style={{ borderColor: "#ff6b6b" }}>
          <strong>Video processing failed.</strong>
          <p className="text-dim">{job.error_message || "Please try processing the video again."}</p>
        </div>
      )}

      {job && (
        <div className="panel" style={{ marginTop: 16 }}>
          {job.steps.map((step) => (
            <div
              key={step.name}
              className="stagger-item"
              style={{ display: "flex", justifyContent: "space-between", padding: "8px 0" }}
            >
              <span>{step.name}</span>
              <span className="text-dim step-row-status" data-status={step.status}>
                {STEP_ICON[step.status]} {step.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
