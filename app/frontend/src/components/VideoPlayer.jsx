import { useRef, useState, useEffect } from "react";

const PLAYBACK_SPEEDS = [0.5, 1, 2];
const ASSUMED_FPS = 25; // used only for the frame-step button

// Field boundaries in 1920x1080 pixel coordinates (matching backend margins)
const FIELD_X1 = 38.4;   // 2% left margin
const FIELD_X2 = 1881.6; // 2% right margin
const FIELD_Y1 = 64.8;   // 6% top margin
const FIELD_Y2 = 1080;   // 0% bottom margin

const isInsideField = (x, y) => {
  return x >= FIELD_X1 && x <= FIELD_X2 && y >= FIELD_Y1 && y <= FIELD_Y2;
};

// Procedural player tracking coordinates generator
function getPositionsAtTime(time) {
  const positions = [];

  // Team A (Red, IDs 1 to 7)
  const teamAPlayers = [
    { id: 1, x0: 180, y0: 540, rx: 15, ry: 40, dx: 15, dy: 35, freq: 0.2 },
    { id: 2, x0: 420, y0: 300, rx: 28, ry: 58, dx: 45, dy: 55, freq: 0.38 },
    { id: 3, x0: 420, y0: 780, rx: 28, ry: 58, dx: 55, dy: 45, freq: 0.28 },
    // Player 4 has large movement range to cross boundary lines and demonstrate the filter
    { id: 4, x0: 250, y0: 200, rx: 32, ry: 68, dx: 260, dy: 160, freq: 0.45 },
    { id: 5, x0: 720, y0: 540, rx: 32, ry: 68, dx: 85, dy: 85, freq: 0.42 },
    { id: 6, x0: 720, y0: 860, rx: 32, ry: 68, dx: 75, dy: 65, freq: 0.32 },
    { id: 7, x0: 1020, y0: 540, rx: 38, ry: 78, dx: 110, dy: 95, freq: 0.55 },
  ];

  // Team B (Blue, IDs 1 to 7)
  const teamBPlayers = [
    { id: 1, x0: 1740, y0: 540, rx: 15, ry: 40, dx: 15, dy: 30, freq: 0.18 },
    { id: 2, x0: 1500, y0: 300, rx: 28, ry: 58, dx: 50, dy: 40, freq: 0.4 },
    { id: 3, x0: 1500, y0: 780, rx: 28, ry: 58, dx: 45, dy: 55, freq: 0.3 },
    { id: 4, x0: 1200, y0: 220, rx: 32, ry: 68, dx: 75, dy: 60, freq: 0.46 },
    { id: 5, x0: 1200, y0: 540, rx: 32, ry: 68, dx: 95, dy: 80, freq: 0.5 },
    { id: 6, x0: 1200, y0: 860, rx: 32, ry: 68, dx: 70, dy: 70, freq: 0.36 },
    { id: 7, x0: 900, y0: 540, rx: 38, ry: 78, dx: 125, dy: 105, freq: 0.52 },
  ];

  teamAPlayers.forEach((p) => {
    const x = p.x0 + Math.sin(time * p.freq + p.id) * p.dx;
    const y = p.y0 + Math.cos(time * p.freq * 1.3 + p.id) * p.dy;
    positions.push({
      id: p.id,
      team: "Team A",
      class_name: "player",
      x,
      y,
      w: p.rx * 2,
      h: p.ry * 2,
    });
  });

  teamBPlayers.forEach((p) => {
    const x = p.x0 + Math.sin(time * p.freq + p.id) * p.dx;
    const y = p.y0 + Math.cos(time * p.freq * 1.3 + p.id) * p.dy;
    positions.push({
      id: p.id,
      team: "Team B",
      class_name: "player",
      x,
      y,
      w: p.rx * 2,
      h: p.ry * 2,
    });
  });

  // Referee (ID 15)
  const refX = 960 + Math.sin(time * 0.28) * 110;
  const refY = 440 + Math.cos(time * 0.33) * 90;
  positions.push({
    id: 15,
    team: "Referee",
    class_name: "referee",
    x: refX,
    y: refY,
    w: 60,
    h: 120,
  });

  // Ball (Yellow)
  const ballFreq = 0.75;
  const ballT = (Math.sin(time * ballFreq) + 1) / 2;
  const p7 = positions.find((pos) => pos.team === "Team A" && pos.id === 7);
  const p14 = positions.find((pos) => pos.team === "Team B" && pos.id === 7);
  if (p7 && p14) {
    const ballX = p7.x * ballT + p14.x * (1 - ballT);
    const ballY = p7.y * ballT + p14.y * (1 - ballT) - Math.abs(Math.sin(time * ballFreq * 2.5)) * 90;
    positions.push({
      id: "ball",
      team: "Ball",
      class_name: "ball",
      x: ballX,
      y: ballY,
      w: 24,
      h: 24,
    });
  }

  return positions;
}

export default function VideoPlayer({
  src,
  overlays = { Players: true, "Player IDs": true, Ball: true, Referee: true },
  selectedId = null,
  onSelect = () => {},
  teamFilter = "All",
  searchFilter = "",
}) {
  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const [rate, setRate] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  function togglePlay() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => {});
      setPlaying(true);
    } else {
      video.pause();
      setPlaying(false);
    }
  }

  // Frame step controls
  function stepFrame(direction) {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setPlaying(false);
    video.currentTime = Math.max(0, video.currentTime + direction * (1 / ASSUMED_FPS));
  }

  function setSpeed(speed) {
    setRate(speed);
    if (videoRef.current) videoRef.current.playbackRate = speed;
  }

  function toggleFullscreen() {
    const container = containerRef.current;
    if (!container) return;

    if (!document.fullscreenElement) {
      container.requestFullscreen().then(() => {
        setIsFullscreen(true);
      }).catch((err) => {
        console.error("Error entering fullscreen:", err);
      });
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  }

  // Handle continuous time updates during playback
  useEffect(() => {
    let animId;
    function update() {
      if (videoRef.current) {
        setCurrentTime(videoRef.current.currentTime);
      }
      animId = requestAnimationFrame(update);
    }
    if (playing) {
      animId = requestAnimationFrame(update);
    } else {
      if (videoRef.current) {
        setCurrentTime(videoRef.current.currentTime);
      }
    }
    return () => cancelAnimationFrame(animId);
  }, [playing]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  // Monitor browser-level fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  // Generate current frame positions and filter them
  const currentPositions = getPositionsAtTime(currentTime);

  const filteredPositions = currentPositions.filter((pos) => {
    // 1. Filter out anyone who is outside the field boundary box (excluding the ball)
    if (pos.class_name === "player" || pos.class_name === "referee") {
      if (!isInsideField(pos.x, pos.y)) {
        return false;
      }
    }

    if (pos.class_name === "player") {
      // 2. Team filter
      if (teamFilter && teamFilter !== "All" && pos.team !== teamFilter) {
        return false;
      }
      // 3. Search filter
      if (searchFilter && searchFilter.trim()) {
        const trackingId = Number(searchFilter.trim().replace(/\D/g, ""));
        if (Number.isFinite(trackingId) && pos.id !== trackingId) {
          return false;
        }
      }
    }
    return true;
  });

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        borderRadius: isFullscreen ? 0 : 10,
        overflow: "hidden",
        background: "#000",
        border: isFullscreen ? "none" : "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        aspectRatio: isFullscreen ? "auto" : "16/9",
        height: isFullscreen ? "100vh" : "auto",
        justifyContent: "space-between",
      }}
    >
      {/* Video + SVG area */}
      <div style={{ position: "relative", flex: 1, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <video
          ref={videoRef}
          src={src}
          controls={false}
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={handleTimeUpdate}
          onSeeked={handleTimeUpdate}
        />

        {/* SVG Player Overlays */}
        <svg
          viewBox="0 0 1920 1080"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
          }}
        >
          {/* Field boundary dashed line */}
          <rect
            x={FIELD_X1}
            y={FIELD_Y1}
            width={FIELD_X2 - FIELD_X1}
            height={FIELD_Y2 - FIELD_Y1}
            fill="none"
            stroke="rgba(255, 255, 255, 0.25)"
            strokeWidth="3.5"
            strokeDasharray="12 12"
          />
          <text
            x={FIELD_X1 + 16}
            y={FIELD_Y1 - 12}
            fill="rgba(255, 255, 255, 0.4)"
            fontSize="14"
            fontWeight="bold"
            letterSpacing="1"
          >
            FIELD BOUNDARY
          </text>

          {filteredPositions.map((pos) => {
            // Apply overlay visibility toggles
            if (pos.class_name === "player" && !overlays["Players"]) return null;
            if (pos.class_name === "referee" && !overlays["Referee"]) return null;
            if (pos.class_name === "ball" && !overlays["Ball"]) return null;

            // Determine core color based on team/status (match composite key)
            const compositeKey = `${pos.team}_${pos.id}`;
            const isSelected = pos.class_name === "player" && compositeKey === selectedId;
            let color = "var(--text-dim)";
            if (pos.class_name === "player") {
              color = pos.team === "Team A" ? "var(--team-a)" : "var(--team-b)";
            } else if (pos.class_name === "ball") {
              color = "#ffeb3b"; // ball color (yellow)
            } else if (pos.class_name === "referee") {
              color = "#e8eaed"; // white-ish
            }

            if (isSelected) {
              color = "var(--accent)";
            }

            const rectX = pos.x - pos.w / 2;
            const rectY = pos.y - pos.h / 2;

            if (pos.class_name === "ball") {
              return (
                <circle
                  key={pos.id}
                  cx={pos.x}
                  cy={pos.y}
                  r={pos.w / 2}
                  fill="rgba(255, 235, 59, 0.4)"
                  stroke={color}
                  strokeWidth="2.5"
                  style={{ filter: "drop-shadow(0px 0px 4px rgba(255, 235, 59, 0.6))" }}
                />
              );
            }

            return (
              <g
                key={compositeKey}
                style={{ cursor: pos.class_name === "player" ? "pointer" : "default", pointerEvents: "auto" }}
                onClick={() => {
                  if (pos.class_name === "player") {
                    onSelect(isSelected ? null : compositeKey);
                  }
                }}
              >
                {/* Player Bounding Box */}
                <rect
                  x={rectX}
                  y={rectY}
                  width={pos.w}
                  height={pos.h}
                  fill={isSelected ? "rgba(61, 220, 132, 0.08)" : "transparent"}
                  stroke={color}
                  strokeWidth={isSelected ? 4 : 2}
                  rx="6"
                  ry="6"
                  style={{
                    transition: "stroke-width 0.1s ease, fill 0.1s ease",
                    filter: isSelected ? "drop-shadow(0px 0px 8px var(--accent))" : "none"
                  }}
                />

                {/* Player/Referee Text Tag */}
                {(pos.class_name === "referee" || (pos.class_name === "player" && overlays["Player IDs"])) && (
                  <g>
                    {/* Tag Background */}
                    <rect
                      x={rectX}
                      y={rectY - 26}
                      width={38}
                      height={20}
                      fill={color}
                      rx="4"
                      ry="4"
                    />
                    {/* Tag Label */}
                    <text
                      x={rectX + 19}
                      y={rectY - 12}
                      textAnchor="middle"
                      fill="#0f1115"
                      fontSize="12"
                      fontWeight="bold"
                    >
                      {pos.class_name === "referee" ? "REF" : pos.id}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Control Buttons */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 16px",
          background: "rgba(23, 26, 33, 0.95)",
          borderTop: "1px solid var(--border)",
          zIndex: 10,
        }}
      >
        <button
          onClick={() => stepFrame(-1)}
          style={{
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: 6,
            color: "var(--text)",
            padding: "4px 10px",
            fontSize: 13,
          }}
        >
          ⏮
        </button>
        <button
          onClick={togglePlay}
          style={{
            background: "var(--accent)",
            border: "none",
            borderRadius: 6,
            color: "#06140c",
            fontWeight: "bold",
            padding: "4px 14px",
            fontSize: 13,
          }}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <button
          onClick={() => stepFrame(1)}
          style={{
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: 6,
            color: "var(--text)",
            padding: "4px 10px",
            fontSize: 13,
          }}
        >
          ⏭
        </button>

        {/* Speed buttons */}
        <div style={{ display: "flex", gap: 4, marginLeft: 16 }}>
          {PLAYBACK_SPEEDS.map((speed) => (
            <button
              key={speed}
              onClick={() => setSpeed(speed)}
              style={{
                background: rate === speed ? "var(--accent)" : "transparent",
                color: rate === speed ? "#06140c" : "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "3px 8px",
                fontSize: 12,
              }}
            >
              {speed}x
            </button>
          ))}
        </div>

        {/* Full screen toggle */}
        <button
          onClick={toggleFullscreen}
          style={{
            marginLeft: "auto",
            background: "transparent",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "4px 12px",
            fontSize: 12,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {isFullscreen ? "Exit Fullscreen" : "📺 Fullscreen"}
        </button>
      </div>
    </div>
  );
}
