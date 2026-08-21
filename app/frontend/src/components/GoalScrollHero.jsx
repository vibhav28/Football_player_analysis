import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

// Same scroll-linked interaction as the Aceternity "macbook-scroll" demo —
// a pinned 3D element that flattens from an angled perspective and zooms
// in as the user scrolls past it, revealing content behind it — but built
// from scratch here (no external component/dependency beyond framer-motion,
// which was already added for this) with a goal net + ball instead of a
// laptop lid + screen.

function SoccerBall({ size = 54 }) {
  const wedgeAngles = [0, 72, 144, 216, 288];
  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      <circle cx="50" cy="50" r="47" fill="#f2f2f0" stroke="#1a1a1a" strokeWidth="2.5" />
      <polygon points="50,32 60,39 56,50 44,50 40,39" fill="#171717" />
      {wedgeAngles.map((angle) => (
        <polygon
          key={angle}
          points="50,6 58,15 54,26 46,26 42,15"
          fill="#171717"
          opacity="0.9"
          transform={`rotate(${angle} 50 50)`}
        />
      ))}
    </svg>
  );
}

function DashboardPreview() {
  const bars = [62, 84, 48, 71, 90, 55];
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent)" }}>GOAL</span>
        <span className="text-dim" style={{ fontSize: 10 }}>Analysis Workspace</span>
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 56 }}>
        {bars.map((h, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: `${h}%`,
              borderRadius: 3,
              background: i % 2 === 0 ? "var(--team-a)" : "var(--team-b)",
              opacity: 0.85,
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
        {[1, 2, 3].map((row) => (
          <div
            key={row}
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 10,
              borderBottom: "1px solid var(--border)",
              paddingBottom: 3,
            }}
          >
            <span className="text-dim">Player {row}</span>
            <span>{(7 + row * 0.6).toFixed(1)} km/h</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function GoalScrollHero() {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });

  // Heading recedes early in the scroll, same beat as the macbook demo's
  // intro copy fading before the lid animation takes over.
  const headingOpacity = useTransform(scrollYProgress, [0, 0.22], [1, 0]);
  const headingY = useTransform(scrollYProgress, [0, 0.22], [0, -50]);

  // Goal net flattens from a tilted angle to face-on and zooms in — the
  // "lid opening" beat, played by the net instead of a laptop screen.
  // Approximated with 2D skew + scaleY rather than true rotateX/perspective
  // 3D transforms: cheaper to composite and avoids GPU 3D-layer rendering
  // issues on lower-end hardware, while reading the same "tilted -> flat" way.
  const netSkew = useTransform(scrollYProgress, [0.15, 0.62], [-10, 0]);
  const netScaleY = useTransform(scrollYProgress, [0.15, 0.62], [0.8, 1]);
  const netScale = useTransform(scrollYProgress, [0.15, 0.75], [0.7, 1.15]);
  const netY = useTransform(scrollYProgress, [0.15, 0.75], [30, -30]);

  // Ball arcs up from the bottom of the frame, spinning, and is "scored"
  // into the net partway through the scroll.
  const ballY = useTransform(scrollYProgress, [0, 0.55], [230, -30]);
  const ballScale = useTransform(scrollYProgress, [0, 0.3, 0.55], [0.55, 1, 0.5]);
  const ballOpacity = useTransform(scrollYProgress, [0.5, 0.63], [1, 0]);
  const ballRotate = useTransform(scrollYProgress, [0, 0.55], [0, 820]);

  // Dashboard mockup revealed behind the net once the ball lands.
  const revealOpacity = useTransform(scrollYProgress, [0.58, 0.82], [0, 1]);

  return (
    <div ref={containerRef} style={{ position: "relative", height: "260vh" }}>
      <div
        style={{
          position: "sticky",
          top: 0,
          height: "100vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background:
            "radial-gradient(ellipse at 50% 30%, rgba(61,220,132,0.06), transparent 60%)",
        }}
      >
        <motion.div
          style={{ opacity: headingOpacity, y: headingY, textAlign: "center", marginBottom: 36, zIndex: 3, padding: "0 24px" }}
        >
          <h2 style={{ fontSize: "clamp(22px, 4vw, 34px)", margin: 0 }}>
            Every Run, Every Sprint, Every Goal — Turned Into Data
          </h2>
          <p className="text-dim" style={{ marginTop: 8 }}>Keep scrolling.</p>
        </motion.div>

        <motion.div
          style={{
            skewX: netSkew,
            scaleY: netScaleY,
            scale: netScale,
            y: netY,
            width: "min(560px, 82vw)",
            height: "min(380px, 56vw)",
            position: "relative",
            zIndex: 2,
          }}
        >
          <svg width="100%" height="100%" viewBox="0 0 560 380" style={{ position: "absolute", inset: 0, overflow: "visible" }}>
            <rect x="16" y="16" width="528" height="12" rx="2" fill="#f4f4f4" />
            <rect x="16" y="16" width="12" height="348" rx="2" fill="#f4f4f4" />
            <rect x="532" y="16" width="12" height="348" rx="2" fill="#f4f4f4" />
            {Array.from({ length: 13 }).map((_, i) => (
              <line
                key={`v${i}`}
                x1={28 + i * 42}
                y1="28"
                x2={28 + i * 42}
                y2="364"
                stroke="rgba(255,255,255,0.22)"
                strokeWidth="1"
              />
            ))}
            {Array.from({ length: 10 }).map((_, i) => (
              <line
                key={`h${i}`}
                x1="28"
                y1={38 + i * 34}
                x2="532"
                y2={38 + i * 34}
                stroke="rgba(255,255,255,0.22)"
                strokeWidth="1"
              />
            ))}
          </svg>

          <motion.div
            style={{
              opacity: revealOpacity,
              position: "absolute",
              inset: "46px 40px",
              borderRadius: 8,
              background: "var(--panel)",
              border: "1px solid var(--border)",
              padding: 16,
              boxShadow: "0 12px 40px rgba(0,0,0,0.35)",
            }}
          >
            <DashboardPreview />
          </motion.div>
        </motion.div>

        <motion.div
          style={{
            position: "absolute",
            left: "50%",
            top: "58%",
            x: "-50%",
            y: ballY,
            scale: ballScale,
            opacity: ballOpacity,
            rotate: ballRotate,
            zIndex: 4,
          }}
        >
          <SoccerBall />
        </motion.div>

        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 64,
            background: "linear-gradient(180deg, transparent, rgba(61,220,132,0.08))",
            borderTop: "1px solid var(--border)",
          }}
        />
      </div>
    </div>
  );
}
