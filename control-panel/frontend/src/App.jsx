import { useState, useEffect } from 'react';
import './index.css';

function App() {
  const [environments, setEnvironments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEnvironments();
    const interval = setInterval(fetchEnvironments, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchEnvironments = async () => {
    try {
      const response = await fetch('/api/environments');
      if (!response.ok) throw new Error('Failed to fetch environments');
      const data = await response.json();
      setEnvironments(data.environments || []);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Could not connect to cluster API');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>Developer Control Panel</h1>
        <p className="subtitle">Active Ephemeral Previews</p>
      </header>

      {loading && environments.length === 0 ? (
        <div className="loader"></div>
      ) : error ? (
        <div style={{ textAlign: 'center', color: 'var(--warning)' }}>{error}</div>
      ) : environments.length === 0 ? (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          No active pull requests found. Open a PR to spin one up!
        </div>
      ) : (
        <div className="envs-grid">
          {environments.map(env => (
            <div className="env-card" key={env.id}>
              <div className="env-header">
                <span className="env-title">{env.name}</span>
                <span className={`status-badge ${env.status.toLowerCase()}`}>
                  {env.status}
                </span>
              </div>
              
              {env.url ? (
                <a href={env.url} target="_blank" rel="noreferrer" className="env-url">
                  {env.url.replace('http://', '')}
                </a>
              ) : (
                <span className="env-url">Waiting for DNS...</span>
              )}
              
              <a 
                href={env.url} 
                target="_blank" 
                rel="noreferrer" 
                className="btn"
                style={{
                  pointerEvents: env.status !== 'Ready' ? 'none' : 'auto',
                  opacity: env.status !== 'Ready' ? 0.5 : 1
                }}
              >
                {env.status === 'Ready' ? 'Open Preview' : 'Deploying...'}
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;
