import { useRef, useState, useEffect } from "react";

const PLAYBACK_SPEEDS = [0.5, 1, 2];
const ASSUMED_FPS = 25; // used only for the frame-step button

// overlays/selectedId/onSelect/teamFilter/searchFilter are accepted but
// currently unused: this component previously drew a procedurally
// animated placeholder overlay (sine/cosine motion, fake field-boundary
// demo) on top of the video regardless of what the video actually
// showed. Once real per-frame tracking data (positions.json) is exposed
// through the API, redraw an SVG overlay here keyed off video.currentTime
// against that real data — not simulated motion — and reconnect these
// props then. Until that exists, showing nothing is more honest than
// showing a fake overlay that visually collides with the backend's own
// baked-in tracking overlay (already present in the annotated video
// itself; see app/pipeline/annotator.py).
export default function VideoPlayer({ src }) {
  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const [rate, setRate] = useState(1);
  const [playing, setPlaying] = useState(false);
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

  // Monitor browser-level fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

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
      <div style={{ position: "relative", flex: 1, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <video
          ref={videoRef}
          src={src}
          controls={false}
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
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
          aria-label="Step back one frame"
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
          aria-label="Step forward one frame"
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
