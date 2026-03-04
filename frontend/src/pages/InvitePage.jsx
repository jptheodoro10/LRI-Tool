import React, { useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from '../services/api';

export default function InvitePage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const query = new URLSearchParams(location.search);

  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [consent, setConsent] = useState(false);
  const [message, setMessage] = useState('');
  const [redirectTarget, setRedirectTarget] = useState('');

  async function join(e) {
    e.preventDefault();
    try {
      const inspect = await api(`/invite/${token}`, 'GET');
      const data = await api(`/invite/${token}/join`, 'POST', { name, company, consent });
      localStorage.setItem('participant', JSON.stringify(data));

      const phase = Number(query.get('phase')) || 2;
      const target = `/projects/${inspect.project_id || data.project_id}/phase/${phase}?mode=participant&participantId=${data.participant_id}`;
      setRedirectTarget(target);
      setMessage('Joined successfully. Redirecting to workshop...');

      setTimeout(() => navigate(target), 900);
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <main className="login-wrap">
      <section className="card login-card">
        <h1>Participant Access</h1>
        <p className="muted">Enter your workshop details</p>
        <form onSubmit={join} className="form-grid">
          <label htmlFor="name">Name</label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} required />

          <label htmlFor="company">Company</label>
          <input id="company" value={company} onChange={(e) => setCompany(e.target.value)} required />

          <label className="checkbox-row">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            I accept consent terms
          </label>

          <button type="submit" className="btn btn-primary">
            Join Workshop
          </button>
          {message && <div className="alert">{message}</div>}
          {redirectTarget && (
            <button type="button" className="btn btn-secondary" onClick={() => navigate(redirectTarget)}>
              Go to Workshop
            </button>
          )}
        </form>
      </section>
    </main>
  );
}
