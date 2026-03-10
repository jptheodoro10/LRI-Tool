import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useAI } from "../context/AIContext";
import logoPUC from "../img/logoPUC.png";

export default function AppShell({
  user,
  onLogout,
  children,
  participantMode = false,
}) {
  const location = useLocation();
  const { aiEnabled, toggleAI } = useAI();
  const participantView = participantMode || location.search.includes("mode=participant");

  return (
    <div className="app-root">
      <header className="topbar">
        <div className="topbar-inner">
          {participantView ? (
            <span className="brand">LRI Tool</span>
          ) : (
            <div>
              {}
              <Link className="brand" to="/dashboard">
                LRI Tool
              </Link>
            </div>
          )}
          <div className="topbar-right">
            {!participantView && (
              <>
                <button
                  className={`btn ${aiEnabled ? "btn-ai-on" : "btn-ai-off"}`}
                  onClick={toggleAI}
                >
                  AI {aiEnabled ? "ON" : "OFF"}
                </button>
                {user && <span className="user-email">{user.email}</span>}
                {user && (
                  <button className="btn btn-ghost" onClick={onLogout}>
                    Logout
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </header>
      <main className="page-shell">
        <div className="page-container">{children}</div>
      </main>
    </div>
  );
}
