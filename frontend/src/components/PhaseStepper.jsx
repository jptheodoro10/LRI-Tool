import React from 'react';

const PHASES = [1, 2, 3, 4, 5];

export default function PhaseStepper({ currentPhaseNumber, activePhaseNumber }) {
  return (
    <aside className="phase-sidebar card">
      <h3>Phases</h3>
      <ul className="phase-list">
        {PHASES.map((phase) => {
          const isCurrent = phase === currentPhaseNumber;
          const isActive = phase === activePhaseNumber;
          const isLocked = phase > currentPhaseNumber;

          return (
            <li
              key={phase}
              className={`phase-item ${isCurrent ? 'current' : ''} ${isActive ? 'active' : ''} ${isLocked ? 'locked' : ''}`}
            >
              <span>Phase {phase}</span>
              {isCurrent ? <span className="phase-badge">Current</span> : isLocked ? <span className="phase-lock">Locked</span> : <span className="phase-dot" />}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
