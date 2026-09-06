import { useState } from "react";

export default function SpeedComparisonChart({ players, selectedId, onSelect }) {
  const [metric, setMetric] = useState("average"); // 'average' or 'max'

  if (!players || players.length === 0) {
    return (
      <div className="panel" style={{ marginTop: 20, textAlign: "center" }}>
        <p className="text-dim">No player statistics available to display chart.</p>
      </div>
    );
  }

  // Find max value in dataset to scale Y axis appropriately
  const speedKey = metric === "average" ? "average_speed_kmh" : "maximum_speed_kmh";
  const maxSpeedVal = Math.max(...players.map((p) => p[speedKey] || 0), 10);
  const yMax = Math.ceil(maxSpeedVal / 5) * 5; // Round up to nearest 5 for clean intervals

  // SVG dimensions
  const width = 800;
  const height = 240;
  const paddingLeft = 40;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 40;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // Render grid lines & Y labels (5 intervals)
  const yTicks = [];
  for (let i = 0; i <= 5; i++) {
    const val = (yMax / 5) * i;
    const y = paddingTop + chartHeight - (val / yMax) * chartHeight;
    yTicks.push({ val, y });
  }

  // tracking_id (1-7) repeats across teams, so match/select on the
  // composite "team_id" key — same format used by PlayerStatsTable and
  // VideoPlayer's overlay.
  const compositeIdOf = (p) => `${p.team}_${p.tracking_id}`;
  const selectedPlayer = players.find((p) => compositeIdOf(p) === selectedId);

  return (
    <div
      className="chart-grid"
      style={{
        gridTemplateColumns: selectedPlayer ? "2.5fr 1fr" : "1fr",
        transition: "grid-template-columns 0.3s ease",
      }}
    >
      {/* Chart Panel */}
      <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Player Speed Comparison</h3>
          
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="icon-btn"
              onClick={() => setMetric("average")}
              style={{
                background: metric === "average" ? "var(--accent)" : "transparent",
                color: metric === "average" ? "#06140c" : "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "6px 12px",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              Average Speed
            </button>
            <button
              className="icon-btn"
              onClick={() => setMetric("max")}
              style={{
                background: metric === "max" ? "var(--accent)" : "transparent",
                color: metric === "max" ? "#06140c" : "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "6px 12px",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              Max Speed
            </button>
          </div>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: "var(--team-a)" }} />
            <span className="text-dim">Team A</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, background: "var(--team-b)" }} />
            <span className="text-dim">Team B</span>
          </div>
          {selectedId && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
              <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, border: "2px solid var(--accent)" }} />
              <span className="text-dim">Selected Player</span>
            </div>
          )}
        </div>

        {/* SVG Chart Container */}
        <div style={{ width: "100%", overflow: "hidden", position: "relative" }}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            width="100%"
            height="100%"
            style={{ display: "block", overflow: "visible" }}
          >
            {/* Gradients */}
            <defs>
              <linearGradient id="grad-team-a" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--team-a)" stopOpacity="1" />
                <stop offset="100%" stopColor="var(--team-a)" stopOpacity="0.6" />
              </linearGradient>
              <linearGradient id="grad-team-b" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--team-b)" stopOpacity="1" />
                <stop offset="100%" stopColor="var(--team-b)" stopOpacity="0.6" />
              </linearGradient>
              <linearGradient id="grad-selected" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity="1" />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.7" />
              </linearGradient>
            </defs>

            {/* Grid & Y Labels */}
            {yTicks.map(({ val, y }) => (
              <g key={val}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  stroke="var(--border)"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 4}
                  textAnchor="end"
                  fill="var(--text-dim)"
                  fontSize="11"
                >
                  {val}
                </text>
              </g>
            ))}

            {/* Bars */}
            {players.map((p, idx) => {
              const barCount = players.length;
              const spacing = chartWidth / barCount;
              const barWidth = Math.max(spacing * 0.6, 12);
              const x = paddingLeft + idx * spacing + (spacing - barWidth) / 2;

              const val = p[speedKey] || 0;
              const barHeight = (val / yMax) * chartHeight;
              const y = paddingTop + chartHeight - barHeight;

              const compositeId = compositeIdOf(p);
              const isSelected = compositeId === selectedId;
              const hasSelection = selectedId !== null;

              // Color determination
              let fill = p.team === "Team A" ? "url(#grad-team-a)" : "url(#grad-team-b)";
              if (isSelected) {
                fill = "url(#grad-selected)";
              }

              return (
                <g
                  key={compositeId}
                  onClick={() => onSelect(isSelected ? null : compositeId)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Invisible tall hover rect for easier clicking */}
                  <rect
                    x={paddingLeft + idx * spacing}
                    y={paddingTop}
                    width={spacing}
                    height={chartHeight}
                    fill="transparent"
                  />
                  {/* Actual Speed Bar */}
                  <rect
                    x={x}
                    y={y}
                    width={barWidth}
                    height={barHeight}
                    fill={fill}
                    rx="4"
                    ry="4"
                    opacity={hasSelection && !isSelected ? 0.35 : 1}
                    style={{
                      transition: "opacity 0.2s ease, fill 0.2s ease, transform 0.2s ease",
                      filter: isSelected ? "drop-shadow(0px 0px 4px var(--accent))" : "none"
                    }}
                  />
                  {/* Selected indicator outline */}
                  {isSelected && (
                    <rect
                      x={x - 2}
                      y={y - 2}
                      width={barWidth + 4}
                      height={barHeight + 4}
                      fill="none"
                      stroke="var(--accent)"
                      strokeWidth="1.5"
                      rx="6"
                      ry="6"
                    />
                  )}
                  {/* Tooltip details when hovering */}
                  <title>{`Player ${p.tracking_id} (${p.team})\nSpeed: ${val.toFixed(2)} km/h\nDistance: ${p.total_distance_m} m`}</title>

                  {/* Player Label on X-axis — team-prefixed since IDs
                      (1-7) repeat across teams and would otherwise be
                      indistinguishable at a glance. */}
                  <text
                    x={x + barWidth / 2}
                    y={paddingTop + chartHeight + 18}
                    textAnchor="middle"
                    fill={isSelected ? "var(--accent)" : "var(--text-dim)"}
                    fontSize="10"
                    fontWeight={isSelected ? "bold" : "normal"}
                  >
                    {p.team === "Team A" ? "A" : "B"}{p.tracking_id}
                  </text>
                </g>
              );
            })}

            {/* Base line */}
            <line
              x1={paddingLeft}
              y1={paddingTop + chartHeight}
              x2={width - paddingRight}
              y2={paddingTop + chartHeight}
              stroke="var(--border)"
              strokeWidth="1.5"
            />
          </svg>
        </div>
      </div>

      {/* Selected Player Details Panel */}
      {selectedPlayer && (
        <div
          className="panel"
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            border: "1px solid var(--accent)",
            animation: "fadeIn 220ms var(--ease-out)"
          }}
        >
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <h4 style={{ margin: 0, fontSize: 16 }}>Player {selectedPlayer.tracking_id}</h4>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
                  <span
                    style={{
                      display: "inline-block",
                      width: 8,
                      height: 8,
                      borderRadius: selectedPlayer.team === "Team A" ? "50%" : "0%",
                      background: selectedPlayer.team === "Team A" ? "var(--team-a)" : "var(--team-b)",
                    }}
                  />
                  <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{selectedPlayer.team}</span>
                </div>
              </div>
              <button
                onClick={() => onSelect(null)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-dim)",
                  fontSize: 18,
                  padding: 0,
                  cursor: "pointer"
                }}
              >
                &times;
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase" }}>Average Speed</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "var(--accent)" }}>
                  {selectedPlayer.average_speed_kmh} <span style={{ fontSize: 13, fontWeight: "normal" }}>km/h</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase" }}>Max Speed</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "#ffb86c" }}>
                  {selectedPlayer.maximum_speed_kmh} <span style={{ fontSize: 13, fontWeight: "normal" }}>km/h</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase" }}>Min Speed</div>
                <div style={{ fontSize: 16, fontWeight: 600 }}>
                  {selectedPlayer.minimum_speed_kmh} <span style={{ fontSize: 11, fontWeight: "normal" }}>km/h</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-dim)", textTransform: "uppercase" }}>Distance Covered</div>
                <div style={{ fontSize: 16, fontWeight: 600 }}>
                  {selectedPlayer.total_distance_m} <span style={{ fontSize: 11, fontWeight: "normal" }}>m</span>
                </div>
              </div>
            </div>
          </div>
          
          <div style={{ fontSize: 11, color: "var(--text-dim)", borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 12 }}>
            Selected on PitchTrack
          </div>
        </div>
      )}
    </div>
  );
}
