"use client";

import { useEffect, useState } from "react";
import { Wind, Play, Pause, X } from "lucide-react";

type BreathingPhase = "inhale" | "hold" | "exhale" | "rest";

interface BreathingGuideProps {
  onClose?: () => void;
  variant?: "floating" | "inline";
}

const PHASES: { phase: BreathingPhase; label: string; subtext: string; duration: number }[] = [
  { phase: "inhale", label: "Inhale slowly", subtext: "Draw peaceful air in through your nose", duration: 4 },
  { phase: "hold", label: "Hold gently", subtext: "Rest comfortably in this still moment", duration: 4 },
  { phase: "exhale", label: "Exhale softly", subtext: "Release all tension through your mouth", duration: 6 },
  { phase: "rest", label: "Be still", subtext: "Feel the calm ground beneath you", duration: 2 },
];

export function BreathingGuide({ onClose, variant = "inline" }: BreathingGuideProps) {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(PHASES[0].duration);
  const [isActive, setIsActive] = useState(true);
  const [cyclesCompleted, setCyclesCompleted] = useState(0);

  const currentPhase = PHASES[phaseIndex];

  useEffect(() => {
    if (!isActive) return;

    const timer = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          const nextIndex = (phaseIndex + 1) % PHASES.length;
          setPhaseIndex(nextIndex);
          if (nextIndex === 0) {
            setCyclesCompleted((c) => c + 1);
          }
          return PHASES[nextIndex].duration;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isActive, phaseIndex]);

  const scale =
    currentPhase.phase === "inhale"
      ? 1.28
      : currentPhase.phase === "hold"
      ? 1.28
      : currentPhase.phase === "exhale"
      ? 0.88
      : 0.95;

  const durationStyle = `${currentPhase.duration}s`;

  return (
    <div className={`breathing-guide-card breathing-guide-${variant}`} role="region" aria-label="Interactive breathing sanctuary">
      <div className="breathing-guide-header">
        <div className="breathing-guide-title-row">
          <span className="breathing-leaf-icon" aria-hidden="true">
            <Wind size={20} />
          </span>
          <div>
            <h3 className="breathing-guide-heading">Calm Breathing Sanctuary</h3>
            <p className="breathing-guide-subheading">4-4-6 grounding rhythm · cycle {cyclesCompleted + 1}</p>
          </div>
        </div>
        <div className="breathing-controls">
          <button
            type="button"
            className="breathing-toggle-btn"
            onClick={() => setIsActive(!isActive)}
            aria-label={isActive ? "Pause breathing exercise" : "Resume breathing exercise"}
            style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}
          >
            {isActive ? (
              <>
                <Pause size={12} /> Pause
              </>
            ) : (
              <>
                <Play size={12} /> Resume
              </>
            )}
          </button>
          {onClose && (
            <button
              type="button"
              className="breathing-close-btn"
              onClick={onClose}
              aria-label="Close breathing guide"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      <div className="breathing-circle-stage">
        {/* Ambient breathing rings */}
        <div
          className={`breathing-ring breathing-ring-outer phase-${currentPhase.phase}`}
          style={{
            transform: `scale(${scale * 1.15})`,
            transition: `transform ${durationStyle} cubic-bezier(0.4, 0, 0.2, 1), opacity ${durationStyle} ease`,
          }}
        />
        <div
          className={`breathing-ring breathing-ring-middle phase-${currentPhase.phase}`}
          style={{
            transform: `scale(${scale * 1.05})`,
            transition: `transform ${durationStyle} cubic-bezier(0.4, 0, 0.2, 1)`,
          }}
        />
        <div
          className={`breathing-circle-core phase-${currentPhase.phase}`}
          style={{
            transform: `scale(${scale})`,
            transition: `transform ${durationStyle} cubic-bezier(0.4, 0, 0.2, 1)`,
          }}
        >
          <span className="breathing-countdown">{secondsLeft}s</span>
        </div>
      </div>

      <div className="breathing-prompt-box">
        <p className="breathing-phase-instruction">{currentPhase.label}</p>
        <p className="breathing-phase-detail">{currentPhase.subtext}</p>
      </div>

      <div className="breathing-step-indicators" aria-hidden="true">
        {PHASES.map((p, idx) => (
          <div
            key={p.phase}
            className={`breathing-step-pill ${idx === phaseIndex ? "is-active" : ""}`}
            title={p.label}
          />
        ))}
      </div>
    </div>
  );
}
