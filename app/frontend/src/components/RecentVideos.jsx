import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { deleteVideo, listVideos } from "../api/client.js";

const STATUS_COLOR = {
  Completed: "var(--accent)",
  Processing: "#ffb86c",
  Uploaded: "var(--text-dim)",
  Failed: "#ff6b6b",
};

// Lets a returning user get back to a past analysis — there's no login/DB
// (PRD section 27), so this is the only way to find a video again without
// already knowing its URL.
export default function RecentVideos() {
  const [videos, setVideos] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    listVideos()
      .then((data) => setVideos(data.sort((a, b) => (a.video_id < b.video_id ? 1 : -1))))
      .catch((err) => setError(err.message));
  }, []);

  async function handleDelete(e, videoId) {
    e.stopPropagation();
    if (!window.confirm("Delete this video and all its analysis results? This can't be undone.")) return;
    try {
      await deleteVideo(videoId);
      setVideos((prev) => prev.filter((v) => v.video_id !== videoId));
    } catch (err) {
      setError(err.message);
    }
  }

  function open(video) {
    if (video.status === "Completed") navigate(`/videos/${video.video_id}/analysis`);
    else if (video.status === "Failed") return; // nothing useful to show yet
    else navigate(`/videos/${video.video_id}/processing`);
  }

  if (error) return null; // backend not reachable yet — fail quietly on the home page
  if (videos === null) return null;
  if (videos.length === 0) return null;

  return (
    <div className="page" style={{ maxWidth: 700, paddingTop: 0 }}>
      <h3 style={{ fontSize: 15, color: "var(--text-dim)", fontWeight: 600, marginBottom: 10 }}>
        Recent videos
      </h3>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        {videos.map((video, i) => (
          <div
            key={video.video_id}
            onClick={() => open(video)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "12px 16px",
              borderTop: i === 0 ? "none" : "1px solid var(--border)",
              cursor: video.status === "Failed" ? "default" : "pointer",
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {video.original_filename}
              </div>
              {video.status === "Failed" && video.error_message && (
                <div style={{ fontSize: 12, color: "#ff6b6b", marginTop: 2 }}>{video.error_message}</div>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
              <span style={{ fontSize: 12, color: STATUS_COLOR[video.status] || "var(--text-dim)" }}>
                {video.status}
              </span>
              <button
                onClick={(e) => handleDelete(e, video.video_id)}
                aria-label="Delete video"
                style={{
                  background: "transparent",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  color: "var(--text-dim)",
                  padding: "3px 8px",
                  fontSize: 12,
                }}
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
