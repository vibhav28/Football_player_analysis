import { useNavigate } from "react-router-dom";
import GoalScrollHero from "../components/GoalScrollHero.jsx";
import RecentVideos from "../components/RecentVideos.jsx";

// PRD section 40, Screen 1 — Home
export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div>
      <div className="page" style={{ textAlign: "center", paddingTop: 80 }}>
        <h1 style={{ fontSize: 42, marginBottom: 8 }}>PitchTrack</h1>
        <p className="text-dim" style={{ fontSize: 18, maxWidth: 560, margin: "0 auto 32px" }}>
          Turn an ordinary football video into player movement statistics —
          tracking, speed, distance, and team breakdowns — using Computer Vision.
        </p>
        <button className="btn-primary" onClick={() => navigate("/upload")}>
          Upload Video
        </button>
      </div>

      <RecentVideos />

      <GoalScrollHero />
    </div>
  );
}
