import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { annotatedVideoUrl, getResults } from "../api/client.js";
import PlayerStatsTable from "../components/PlayerStatsTable.jsx";
import VideoPlayer from "../components/VideoPlayer.jsx";
import SpeedComparisonChart from "../components/SpeedComparisonChart.jsx";

const OVERLAY_TOGGLES = ["Players", "Player IDs", "Ball", "Referee"];

// PRD section 40, Screen 4 — Analysis Workspace
export default function AnalysisPage() {
  const { videoId } = useParams();
  const [video, setVideo] = useState(null);
  const [players, setPlayers] = useState([]);
  const [ballStats, setBallStats] = useState(null);
  const [error, setError] = useState(null);

  const [team, setTeam] = useState("All");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [overlays, setOverlays] = useState(
    Object.fromEntries(OVERLAY_TOGGLES.map((name) => [name, true])),
  );

  useEffect(() => {
    const trackingId = search.trim() ? Number(search.trim().replace(/\D/g, "")) : undefined;

    getResults(videoId, {
      team,
      tracking_id: Number.isFinite(trackingId) ? trackingId : undefined,
    })
      .then((data) => {
        setVideo(data.video);
        setPlayers(data.players);
        setBallStats(data.ball);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, [videoId, team, search]);

  return (
    <div className="page" style={{ maxWidth: 1300 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>{video?.filename || "Analysis"}</h2>
        <Link to={`/videos/${videoId}/export`} className="btn-primary" style={{ textDecoration: "none" }}>
          Export
        </Link>
      </div>

      {error && <p style={{ color: "#ff6b6b" }}>{error}</p>}

      {/* Top: team filter + overlay controls (PRD sections 21, 23) */}
      <div className="panel" style={{ display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
        <label>
          Team:{" "}
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            <option>All</option>
            <option>Team A</option>
            <option>Team B</option>
          </select>
        </label>

        <label>
          Search player:{" "}
          <input
            placeholder="e.g. 12"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 80 }}
          />
        </label>

        <div style={{ display: "flex", gap: 12 }}>
          {OVERLAY_TOGGLES.map((name) => (
            <label key={name} className="text-dim" style={{ fontSize: 13 }}>
              <input
                type="checkbox"
                checked={overlays[name]}
                onChange={(e) => setOverlays({ ...overlays, [name]: e.target.checked })}
              />{" "}
              {name}
            </label>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 20, marginTop: 20 }}>
        <div>
          <VideoPlayer
            src={annotatedVideoUrl(videoId)}
            overlays={overlays}
            selectedId={selectedId}
            onSelect={setSelectedId}
            teamFilter={team}
            searchFilter={search}
          />
        </div>

        <div className="panel">
          {ballStats && (
            <div
              style={{
                background: "rgba(255, 235, 59, 0.05)",
                border: "1px solid rgba(255, 235, 59, 0.2)",
                borderRadius: 8,
                padding: "12px 16px",
                marginBottom: 16,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: "#ffeb3b",
                    boxShadow: "0 0 6px #ffeb3b",
                  }}
                />
                <h4 style={{ margin: 0, fontSize: 14, color: "#ffeb3b" }}>Ball Live Tracking</h4>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <div>
                  <span className="text-dim">Avg Speed: </span>
                  <strong>{ballStats.average_speed_kmh} km/h</strong>
                </div>
                <div>
                  <span className="text-dim">Max Speed: </span>
                  <strong>{ballStats.maximum_speed_kmh} km/h</strong>
                </div>
                <div>
                  <span className="text-dim">Distance: </span>
                  <strong>{ballStats.total_distance_m} m</strong>
                </div>
              </div>
            </div>
          )}
          <PlayerStatsTable players={players} selectedId={selectedId} onSelect={setSelectedId} />
        </div>
      </div>

      {/* Bottom: speed comparison chart */}
      <SpeedComparisonChart
        players={players}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
    </div>
  );
}
