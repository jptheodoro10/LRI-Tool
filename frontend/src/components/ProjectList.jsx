import React from 'react';
import { Link } from 'react-router-dom';
import { enumToPhaseNumber } from '../config/phaseConfig';

export default function ProjectList({ projects }) {
  return (
    <div className="project-list">
      {projects.map((project) => {
        const phaseNumber = enumToPhaseNumber(project.current_phase);
        return (
          <Link key={project.id} to={`/projects/${project.id}/phase/${phaseNumber}`} className="project-row">
            <div>
              <h3>{project.title}</h3>
              <p>
                Status: <strong>{project.current_phase}</strong>
              </p>
              {project.created_at && <p className="muted">Created: {new Date(project.created_at).toLocaleDateString()}</p>}
            </div>
            <span className="row-arrow">Open</span>
          </Link>
        );
      })}
    </div>
  );
}
