import { Link, useParams } from "react-router-dom";
import { exportUrl } from "../api/client.js";

// PRD section 40, Screen 5 — Export
export default function ExportPage() {
  const { videoId } = useParams();

  return (
    <div className="page">
      <Link to={`/videos/${videoId}/analysis`} className="text-dim">
        ← Back to analysis
      </Link>
      <h2>Export Statistics</h2>

      <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 360 }}>
        <a className="btn-primary" style={{ textDecoration: "none", textAlign: "center" }} href={exportUrl(videoId, "csv")}>
          Download CSV
        </a>
        <a className="btn-primary" style={{ textDecoration: "none", textAlign: "center" }} href={exportUrl(videoId, "json")}>
          Download JSON
        </a>
        <a
          className="btn-primary"
          style={{ textDecoration: "none", textAlign: "center" }}
          href={exportUrl(videoId, "annotated-video")}
        >
          Download Annotated Video
        </a>
      </div>
      <p className="text-dim" style={{ marginTop: 16 }}>
        CSV/JSON exports reflect the filters currently applied in the Analysis
        Workspace (team, player, time window) — set them there before exporting.
      </p>
    </div>
  );
}
