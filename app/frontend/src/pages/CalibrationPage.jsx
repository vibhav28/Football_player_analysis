import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { calibrateVideo, originalVideoUrl } from "../api/client.js";

const CORNER_LABELS = ["top-left", "top-right", "bottom-right", "bottom-left"];
// Mirrors app/backend/schemas.py's MATCH_FORMAT_PRESETS keys/order — the
// backend resolves the actual player-count/pitch-size numbers from
// match_format itself, this is just the dropdown's label list.
const MATCH_FORMAT_OPTIONS = [
  { value: "", label: "Not specified (safe default)" },
  { value: "5v5", label: "5-a-side (5v5)" },
  { value: "7v7", label: "7-a-side (7v7)" },
  { value: "9v9", label: "9-a-side (9v9)" },
  { value: "11v11", label: "11-a-side (11v11, standard full pitch)" },
  { value: "custom", label: "Custom…" },
];
const ASSUMED_FPS = 25; // used only for the frame-step buttons' step size
// How close video.currentTime has to be to a point's own timestamp for
// that point's marker to be drawn on the current frame — points from
// other frames stay hidden rather than drawn in the wrong place.
const SAME_FRAME_TOLERANCE_SECONDS = 1 / ASSUMED_FPS;

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// PRD section 35, Perspective Calibration — the step between Upload and
// Processing. No single frame necessarily shows all four pitch corners
// (broadcast cameras pan/zoom), so each of the 4 corners can be placed on
// whatever frame is on screen when it's clicked — 4 from one frame, or
// each from a different frame, or any mix. Every point carries its own
// timestamp; the backend compensates each one individually for camera
// motion back to a common coordinate space (see run_pipeline.py), so it
// doesn't matter that they may come from different moments in the video.
export default function CalibrationPage() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [videoReady, setVideoReady] = useState(false);

  const [points, setPoints] = useState([]); // [{x, y, time}, ...] in click order

  const [matchFormat, setMatchFormat] = useState(""); // "" = not specified
  const [customPlayers, setCustomPlayers] = useState("");
  const [customWidth, setCustomWidth] = useState("");
  const [customLength, setCustomLength] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Canvas native size only needs setting once metadata is known.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    function onLoadedMetadata() {
      const canvas = canvasRef.current;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      setDuration(video.duration || 0);
      setVideoReady(true);
    }

    video.addEventListener("loadedmetadata", onLoadedMetadata);
    return () => video.removeEventListener("loadedmetadata", onLoadedMetadata);
  }, []);

  // Redraw the current frame, plus markers for any points that were
  // placed on (approximately) this same frame — a point placed elsewhere
  // stays hidden until the user scrubs back to it, rather than being
  // drawn at a pixel position that has nothing to do with what's on
  // screen right now.
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !videoReady) return;

    function draw() {
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      setCurrentTime(video.currentTime);

      const visible = points
        .map((p, i) => ({ ...p, index: i }))
        .filter((p) => Math.abs(p.time - video.currentTime) <= SAME_FRAME_TOLERANCE_SECONDS);

      if (visible.length > 1) {
        ctx.beginPath();
        ctx.moveTo(visible[0].x, visible[0].y);
        for (let i = 1; i < visible.length; i++) ctx.lineTo(visible[i].x, visible[i].y);
        ctx.strokeStyle = "#4ade80";
        ctx.lineWidth = Math.max(2, canvas.width / 400);
        ctx.stroke();
      }

      visible.forEach(({ x, y, index }) => {
        const radius = Math.max(6, canvas.width / 150);
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = "#4ade80";
        ctx.fill();
        ctx.strokeStyle = "#06140c";
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = "#fff";
        ctx.font = `bold ${Math.max(14, canvas.width / 60)}px sans-serif`;
        ctx.fillText(String(index + 1), x + radius + 4, y - radius - 4);
      });
    }

    draw();
    video.addEventListener("loadeddata", draw);
    video.addEventListener("timeupdate", draw);
    video.addEventListener("seeked", draw);
    return () => {
      video.removeEventListener("loadeddata", draw);
      video.removeEventListener("timeupdate", draw);
      video.removeEventListener("seeked", draw);
    };
  }, [videoReady, points]);

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

  function seekTo(seconds) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Math.max(0, Math.min(duration, seconds));
  }

  function stepFrame(direction) {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setPlaying(false);
    seekTo(video.currentTime + (direction * 1) / ASSUMED_FPS);
  }

  function handleCanvasClick(e) {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || points.length >= 4 || submitting) return;

    // Pin down the exact frame being clicked on — if the video is still
    // playing, clicking means "this is the frame I meant", so pause it
    // right here rather than let it keep drifting past the intended point.
    if (!video.paused) {
      video.pause();
      setPlaying(false);
    }

    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((e.clientY - rect.top) / rect.height) * canvas.height;
    setPoints((prev) => [...prev, { x, y, time: video.currentTime }]);
  }

  function undoLastPoint() {
    setPoints((prev) => prev.slice(0, -1));
  }

  async function submit(corners) {
    setSubmitting(true);
    setError(null);
    try {
      // Match format is independent of whether pitch corners were
      // supplied — a 7v7 match that skips calibration should still get
      // players_per_team=7 even though speed/distance stay 0.
      await calibrateVideo(videoId, corners, {
        matchFormat: matchFormat || null,
        playersPerTeam: matchFormat === "custom" && customPlayers ? Number(customPlayers) : null,
        pitchWidthM: matchFormat === "custom" && customWidth ? Number(customWidth) : null,
        pitchLengthM: matchFormat === "custom" && customLength ? Number(customLength) : null,
      });
      navigate(`/videos/${videoId}/processing`);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <h2>Calibrate Pitch</h2>
      <p className="text-dim" style={{ maxWidth: 640 }}>
        Find moments in the video where you can see the four corners of the{" "}
        <strong>full pitch</strong> — where each sideline meets each goal line.
        They don't have to be the same frame: scrub or play, click a corner
        wherever you can see it, then scrub to a different moment for the
        next one if you need to. Click in order:{" "}
        <strong>top-left, top-right, bottom-right, bottom-left</strong>. Pick
        your match format below so distances scale to the right pitch size —
        the default assumes a standard 105m &times; 68m 11-a-side pitch
        unless you choose otherwise.
      </p>
      <p className="text-dim" style={{ maxWidth: 640, fontSize: 13 }}>
        If no frame shows a given corner at all, skip calibration instead of
        guessing — tracking, team classification, and the annotated video
        will still be produced, just with speed and distance reading 0.
      </p>

      <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label>
          Match format:{" "}
          <select value={matchFormat} onChange={(e) => setMatchFormat(e.target.value)}>
            {MATCH_FORMAT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        {matchFormat === "custom" && (
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <label>
              Players per team:{" "}
              <input
                type="number"
                min="1"
                max="30"
                value={customPlayers}
                onChange={(e) => setCustomPlayers(e.target.value)}
                style={{ width: 60 }}
              />
            </label>
            <label>
              Pitch width (m):{" "}
              <input
                type="number"
                min="10"
                max="100"
                value={customWidth}
                onChange={(e) => setCustomWidth(e.target.value)}
                style={{ width: 70 }}
              />
            </label>
            <label>
              Pitch length (m):{" "}
              <input
                type="number"
                min="15"
                max="130"
                value={customLength}
                onChange={(e) => setCustomLength(e.target.value)}
                style={{ width: 70 }}
              />
            </label>
          </div>
        )}
      </div>

      <div className="panel" style={{ padding: 0, overflow: "hidden", position: "relative" }}>
        <video
          ref={videoRef}
          src={originalVideoUrl(videoId)}
          muted
          preload="metadata"
          style={{ display: "none" }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
        {!videoReady && (
          <div style={{ padding: 48, textAlign: "center" }} className="text-dim">
            Loading video…
          </div>
        )}
        <canvas
          ref={canvasRef}
          onClick={handleCanvasClick}
          style={{
            width: "100%",
            display: videoReady ? "block" : "none",
            cursor: points.length < 4 ? "crosshair" : "default",
          }}
        />

        {videoReady && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "10px 16px",
              background: "rgba(23, 26, 33, 0.95)",
              borderTop: "1px solid var(--border)",
            }}
          >
            <button className="icon-btn" onClick={() => stepFrame(-1)} aria-label="Step back one frame">
              ⏮
            </button>
            <button className="icon-btn" onClick={togglePlay}>{playing ? "Pause" : "Play"}</button>
            <button className="icon-btn" onClick={() => stepFrame(1)} aria-label="Step forward one frame">
              ⏭
            </button>
            <span className="text-dim" style={{ fontSize: 12, minWidth: 40 }}>
              {formatTime(currentTime)}
            </span>
            <input
              type="range"
              min={0}
              max={duration || 0}
              step={0.01}
              value={currentTime}
              onChange={(e) => seekTo(Number(e.target.value))}
              style={{ flex: 1 }}
            />
            <span className="text-dim" style={{ fontSize: 12, minWidth: 40 }}>
              {formatTime(duration)}
            </span>
          </div>
        )}
      </div>

      <div style={{ marginTop: 12 }}>
        {CORNER_LABELS.map((label, i) => {
          const p = points[i];
          return (
            <div
              key={label}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "6px 0",
                borderTop: i === 0 ? "none" : "1px solid var(--border)",
              }}
            >
              <span className={p ? "" : "text-dim"}>
                {i + 1}. {label}
                {p ? ` — placed at ${formatTime(p.time)}` : " — not placed yet"}
              </span>
              {p && (
                <button onClick={() => seekTo(p.time)} style={{ fontSize: 12 }}>
                  Jump to frame
                </button>
              )}
            </div>
          );
        })}
      </div>

      {error && <p style={{ color: "#ff6b6b" }}>{error}</p>}

      <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
        <button
          className="btn-primary"
          disabled={points.length !== 4 || submitting}
          onClick={() => submit(points)}
        >
          {submitting ? "Starting…" : "Confirm & Start Analysis"}
        </button>
        <button className="icon-btn" disabled={points.length === 0 || submitting} onClick={undoLastPoint}>
          Undo point
        </button>
        <button
          className="icon-btn"
          disabled={submitting}
          onClick={() => submit(null)}
          style={{ marginLeft: "auto" }}
        >
          Skip calibration
        </button>
      </div>
    </div>
  );
}
