import { useState, useEffect } from 'react';
import './index.css';

function App() {
  const [environments, setEnvironments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEnvironments();
    const interval = setInterval(fetchEnvironments, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchEnvironments = async () => {
    try {
      const res = await fetch('/api/environments');
      const data = await res.json();
      setEnvironments(data.environments || []);
    } catch (err) {
      console.error("Failed to load environments", err);
    } finally {
      setLoading(false);
    }
  };

  const timeAgo = (dateString) => {
    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    const daysDifference = Math.round((new Date(dateString) - new Date()) / (1000 * 60 * 60 * 24));
    return rtf.format(daysDifference, 'day');
  };

  return (
    <div className="layout">
      <header>
        <div className="brand">Deployments</div>
      </header>

      <main>
        {loading && environments.length === 0 ? (
          <div className="empty-state">Loading environments...</div>
        ) : environments.length === 0 ? (
          <div className="empty-state">
            <p>No active pull requests found.</p>
          </div>
        ) : (
          <div className="environments-list">
            {environments.map(env => (
              <div className="env-card" key={env.id}>
                <div className="env-info">
                  <div className="env-title">{env.name}</div>
                  <div className="env-meta">
                    <span className={`badge ${env.status.toLowerCase()}`}>
                      {env.status}
                    </span>
                    <span>Created {timeAgo(env.created_at)}</span>
                  </div>
                </div>
                
                <a 
                  href={env.url} 
                  target="_blank" 
                  rel="noreferrer" 
                  className="btn"
                  style={env.status !== 'Ready' ? { pointerEvents: 'none', opacity: 0.5 } : {}}
                >
                  Visit Deployment
                </a>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
