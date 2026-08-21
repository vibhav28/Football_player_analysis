import { Route, Routes } from "react-router-dom";
import AnalysisPage from "./pages/AnalysisPage.jsx";
import ExportPage from "./pages/ExportPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import ProcessingPage from "./pages/ProcessingPage.jsx";
import UploadPage from "./pages/UploadPage.jsx";

// Route layout mirrors the PRD's core user flow (section 8):
// Home -> Upload -> Processing -> Analysis Workspace -> Export
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/videos/:videoId/processing" element={<ProcessingPage />} />
      <Route path="/videos/:videoId/analysis" element={<AnalysisPage />} />
      <Route path="/videos/:videoId/export" element={<ExportPage />} />
    </Routes>
  );
}
