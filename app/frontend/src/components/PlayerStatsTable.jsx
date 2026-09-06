import { useState } from "react";

const COLUMNS = [
  { key: "tracking_id", label: "Player" },
  { key: "team", label: "Team" },
  { key: "average_speed_kmh", label: "Avg Speed" },
  { key: "minimum_speed_kmh", label: "Min Speed" },
  { key: "maximum_speed_kmh", label: "Max Speed" },
  { key: "total_distance_m", label: "Distance" },
];

// PRD section 19, Player Statistics table + section 22, Player Selection
export default function PlayerStatsTable({ players, selectedId, onSelect }) {
  const [sortKey, setSortKey] = useState("tracking_id");
  const [sortDir, setSortDir] = useState("asc");

  if (players.length === 0) {
    return <p className="text-dim">No players match the current filters.</p>;
  }

  function toggleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const sorted = [...players].sort((a, b) => {
    const mult = sortDir === "asc" ? 1 : -1;
    if (a[sortKey] < b[sortKey]) return -mult;
    if (a[sortKey] > b[sortKey]) return mult;
    return 0;
  });

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
          {COLUMNS.map((col, i) => (
            <th
              key={col.key}
              onClick={() => toggleSort(col.key)}
              style={{ padding: i === 0 ? "8px 6px" : undefined, cursor: "pointer", userSelect: "none" }}
            >
              {col.label} {sortKey === col.key ? (sortDir === "asc" ? "▲" : "▼") : ""}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((p) => {
          // Composite key: tracking_id (1-7) repeats across teams, so
          // "team_id" is what uniquely identifies a player — matches the
          // selectedId format used by VideoPlayer and SpeedComparisonChart.
          const compositeId = `${p.team}_${p.tracking_id}`;
          return (
          <tr
            key={compositeId}
            onClick={() => onSelect(compositeId === selectedId ? null : compositeId)}
            style={{
              cursor: "pointer",
              borderBottom: "1px solid var(--border)",
              background: compositeId === selectedId ? "rgba(61,220,132,0.12)" : "transparent",
            }}
          >
            <td style={{ padding: "8px 6px" }}>
              <span
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: p.team === "Team A" ? "50%" : "0%",
                  background: p.team === "Team A" ? "var(--team-a)" : "var(--team-b)",
                  marginRight: 8,
                }}
              />
              Player {p.tracking_id}
            </td>
            <td>{p.team}</td>
            <td>{p.average_speed_kmh} km/h</td>
            <td>{p.minimum_speed_kmh} km/h</td>
            <td>{p.maximum_speed_kmh} km/h</td>
            <td>{p.total_distance_m} m</td>
          </tr>
          );
        })}
      </tbody>
    </table>
  );
}
