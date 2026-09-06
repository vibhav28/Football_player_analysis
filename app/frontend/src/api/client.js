const BASE_URL = "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function uploadVideo(file, onProgress) {
  // Uses XHR instead of fetch so we get upload progress events (PRD 9.1).
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_URL}/api/videos/upload`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        const detail = JSON.parse(xhr.responseText || "{}").detail;
        reject(new Error(detail || `Upload failed: ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed: network error"));
    xhr.send(formData);
  });
}

export const getStatus = (videoId) => request(`/api/videos/${videoId}/status`);

// pitchPixelCorners: 4 { x, y, time } points (or null to skip calibration),
// ordered top-left, top-right, bottom-right, bottom-left. Each point
// carries its own timestamp — they don't all have to come from the same
// frame, since no single frame necessarily shows all four pitch corners
// (PRD section 35).
//
// matchFormat (optional): { matchFormat, playersPerTeam, pitchWidthM,
// pitchLengthM } — selects the match's real per-team player count and
// pitch size (see app/backend/schemas.py's MATCH_FORMAT_PRESETS), so a
// 7v7 or 9v9 match doesn't get its player count/speed-distance figures
// computed as if it were a full 11-a-side match.
export const calibrateVideo = (videoId, pitchPixelCorners, matchFormat = {}) =>
  request(`/api/videos/${videoId}/calibrate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pitch_pixel_corners: pitchPixelCorners
        ? pitchPixelCorners.map((p) => ({ x: p.x, y: p.y, time_seconds: p.time }))
        : null,
      match_format: matchFormat.matchFormat ?? null,
      players_per_team: matchFormat.playersPerTeam ?? null,
      pitch_width_m: matchFormat.pitchWidthM ?? null,
      pitch_length_m: matchFormat.pitchLengthM ?? null,
    }),
  });

export const listVideos = () => request("/api/videos");

export const getResults = (videoId, filters = {}) => {
  const params = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  );
  const query = params.toString() ? `?${params.toString()}` : "";
  return request(`/api/videos/${videoId}/results${query}`);
};

export const getPositions = (videoId) => request(`/api/videos/${videoId}/positions`);

export const deleteVideo = (videoId) =>
  request(`/api/videos/${videoId}`, { method: "DELETE" });

export const originalVideoUrl = (videoId) => `${BASE_URL}/api/videos/${videoId}/video`;
export const annotatedVideoUrl = (videoId) => `${BASE_URL}/api/videos/${videoId}/annotated`;

export const exportUrl = (videoId, format, filters = {}) => {
  const params = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  );
  const query = params.toString() ? `?${params.toString()}` : "";
  return `${BASE_URL}/api/videos/${videoId}/export/${format}${query}`;
};
