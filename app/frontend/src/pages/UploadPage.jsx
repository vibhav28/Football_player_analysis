import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadVideo } from "../api/client.js";

const ALLOWED_EXTENSIONS = [".mp4", ".mov", ".avi"];

// PRD section 40, Screen 2 — Upload (drag-and-drop, browse, progress, validation message)
export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  function pickFile(candidate) {
    const ext = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported or corrupted video file. Supported formats: ${ALLOWED_EXTENSIONS.join(", ")}`);
      return;
    }
    setError(null);
    setFile(candidate);
  }

  async function startUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadVideo(file, setProgress);
      navigate(`/videos/${result.video_id}/processing`);
    } catch (err) {
      setError(err.message);
      setUploading(false);
    }
  }

  return (
    <div className="page">
      <h2>Upload Video</h2>

      <div
        className="panel"
        style={{
          borderStyle: "dashed",
          textAlign: "center",
          padding: 48,
          cursor: "pointer",
        }}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (e.dataTransfer.files[0]) pickFile(e.dataTransfer.files[0]);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(",")}
          style={{ display: "none" }}
          onChange={(e) => e.target.files[0] && pickFile(e.target.files[0])}
        />
        {file ? (
          <div>
            <div>{file.name}</div>
            <div className="text-dim">{(file.size / (1024 * 1024)).toFixed(1)} MB</div>
          </div>
        ) : (
          <div className="text-dim">Drag and drop a video here, or click to browse</div>
        )}
      </div>

      {error && (
        <p style={{ color: "#ff6b6b", marginTop: 16 }}>{error}</p>
      )}

      {uploading && (
        <div style={{ marginTop: 16 }}>
          <div className="text-dim">Uploading... {progress}%</div>
          <div style={{ background: "var(--border)", borderRadius: 4, height: 8, marginTop: 6 }}>
            <div
              style={{
                width: `${progress}%`,
                background: "var(--accent)",
                height: "100%",
                borderRadius: 4,
                transition: "width 0.2s",
              }}
            />
          </div>
        </div>
      )}

      <button
        className="btn-primary"
        style={{ marginTop: 20 }}
        disabled={!file || uploading}
        onClick={startUpload}
      >
        {uploading ? "Uploading..." : "Start Analysis"}
      </button>
    </div>
  );
}
