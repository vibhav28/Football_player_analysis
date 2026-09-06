import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { annotatedVideoUrl, getResults } from "../api/client.js";
import PlayerStatsTable from "../components/PlayerStatsTable.jsx";
import VideoPlayer from "../components/VideoPlayer.jsx";
import SpeedComparisonChart from "../components/SpeedComparisonChart.jsx";

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Picks the player with the highest value for `key`, or null if there are
// none — avoids a plain Array.reduce blowing up / returning garbage on an
// empty players list (e.g. a video with zero surviving tracks).
function topPlayerBy(players, key) {
  return players.reduce((best, p) => (best === null || p[key] > best[key] ? p : best), null);
}

// PRD section 40, Screen 4 — Analysis Workspace
export default function AnalysisPage() {
  const { videoId } = useParams();
  const [video, setVideo] = useState(null);
  const [players, setPlayers] = useState([]);
  const [ballStats, setBallStats] = useState(null);
  const [possession, setPossession] = useState(null);
  const [error, setError] = useState(null);

  const [team, setTeam] = useState("All");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);

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
        setPossession(data.possession);
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

      {video && video.pitch_calibrated === false && (
        <div
          className="panel"
          style={{
            borderColor: "rgba(255, 184, 108, 0.4)",
            background: "rgba(255, 184, 108, 0.06)",
            fontSize: 13,
            padding: "10px 16px",
          }}
        >
          <strong style={{ color: "#ffb86c" }}>Speed and distance unavailable.</strong>{" "}
          <span className="text-dim">
            This video hasn't been pitch-calibrated, so meters-per-pixel is unknown — figures below read 0
            rather than a guess. Tracking, team classification, and the annotated video are unaffected.
          </span>
        </div>
      )}

      {/* Team filter (PRD section 23) */}
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
      </div>

      {/* Match-at-a-glance KPI strip — computed client-side from the same
          /results payload already fetched above, no extra request. */}
      <div className="stat-grid" style={{ marginTop: 20 }}>
        <div className="stat-tile">
          <div className="stat-tile-label">Players Tracked</div>
          <div className="stat-tile-value">{players.length}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-tile-label">Match Duration</div>
          <div className="stat-tile-value">{video ? formatDuration(video.duration) : "—"}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-tile-label">Top Speed</div>
          {(() => {
            const top = topPlayerBy(players, "maximum_speed_kmh");
            return (
              <>
                <div className="stat-tile-value">{top ? `${top.maximum_speed_kmh} km/h` : "—"}</div>
                {top && <div className="stat-tile-sub">Player {top.tracking_id} ({top.team})</div>}
              </>
            );
          })()}
        </div>
        <div className="stat-tile">
          <div className="stat-tile-label">Distance Leader</div>
          {(() => {
            const leader = topPlayerBy(players, "total_distance_m");
            return (
              <>
                <div className="stat-tile-value">{leader ? `${leader.total_distance_m} m` : "—"}</div>
                {leader && <div className="stat-tile-sub">Player {leader.tracking_id} ({leader.team})</div>}
              </>
            );
          })()}
        </div>
        <div className="stat-tile">
          <div className="stat-tile-label">Possession Lead</div>
          <div className="stat-tile-value">
            {possession
              ? (() => {
                  const [team, pct] = Object.entries(possession).reduce((a, b) => (b[1] > a[1] ? b : a));
                  return `${team} ${pct}%`;
                })()
              : "—"}
          </div>
        </div>
      </div>

      <div className="analysis-grid">
        <div>
          <VideoPlayer src={annotatedVideoUrl(videoId)} />
        </div>

        <div className="panel">
          {possession && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Possession</h4>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                <span>Team A {possession["Team A"] ?? 0}%</span>
                <span>Team B {possession["Team B"] ?? 0}%</span>
              </div>
              <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${possession["Team A"] ?? 0}%`, background: "var(--team-a)" }} />
                <div style={{ width: `${possession["Team B"] ?? 0}%`, background: "var(--team-b)" }} />
              </div>
            </div>
          )}
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
