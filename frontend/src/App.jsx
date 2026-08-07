import { useEffect, useState } from 'react'

function App() {
  const [tasks, setTasks] = useState([])
  const [health, setHealth] = useState(null)
  const [newTask, setNewTask] = useState('')
  const [loading, setLoading] = useState(true)

  // Determine dynamic hue based on PR number for environment color isolation
  const prNumber = health?.pr || '0'
  const envHue = (parseInt(prNumber) * 47) % 360

  useEffect(() => {
    // Set CSS variable for dynamic theming
    document.documentElement.style.setProperty('--env-hue', envHue)
  }, [envHue])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [tasksRes, healthRes] = await Promise.all([
        fetch('/api/tasks'),
        fetch('/api/health')
      ])
      const tasksData = await tasksRes.json()
      const healthData = await healthRes.json()
      
      setTasks(tasksData)
      setHealth(healthData)
      setLoading(false)
    } catch (err) {
      console.error("Failed to fetch API:", err)
      setLoading(false)
    }
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!newTask.trim()) return

    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTask })
    })
    
    if (res.ok) {
      const task = await res.json()
      setTasks([...tasks, task])
      setNewTask('')
    }
  }

  const handleToggle = async (id) => {
    // Optimistic UI update
    setTasks(tasks.map(t => t.id === id ? { ...t, done: !t.done } : t))
    await fetch(`/api/tasks/${id}/toggle`, { method: 'POST' })
    fetchData() // Sync with server
  }

  const handleDelete = async (id) => {
    setTasks(tasks.filter(t => t.id !== id))
    await fetch(`/api/tasks/${id}/delete`, { method: 'POST' })
  }

  if (loading) {
    return (
      <div className="window" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
        <div className="loader"></div>
      </div>
    )
  }

  return (
    <div className="window">
      <div className="titlebar">
        <div className="traffic">
          <div className="dot dot-red"></div>
          <div className="dot dot-yellow"></div>
          <div className="dot dot-green"></div>
        </div>
        <div className="titlebar-center">DevBoard — {health?.env || 'Local'} (React)</div>
      </div>

      <div className="content">
        <div className="env-pill">
          <div className="env-dot"></div>
          <span className="env-pill-text">PR #{health?.pr || '0'} · Live Preview</span>
        </div>

        <div className="section">
          <div className="section-header">
            <span className="section-title">New Task</span>
          </div>
          <div className="section-body">
            <form className="add-form" onSubmit={handleAdd}>
              <input 
                className="add-input" 
                value={newTask} 
                onChange={e => setNewTask(e.target.value)}
                placeholder="What needs to be done?" 
                required 
              />
              <button className="add-btn" type="submit">Add</button>
            </form>
          </div>
        </div>

        <div className="section">
          <div className="section-header">
            <span className="section-title">PR Preview</span>
            <span className="count-badge">{tasks.length}</span>
          </div>
          <div className="section-body">
            {tasks.length === 0 ? (
              <div className="empty-state">No tasks yet</div>
            ) : (
              <ul className="task-list">
                {tasks.map(t => (
                  <li key={t.id} className={`task-item ${t.title.startsWith('[System]') ? 'seed-task' : ''}`}>
                    <button 
                      className={`check-btn ${t.done ? 'checked' : ''}`}
                      onClick={() => handleToggle(t.id)}
                    >
                      {t.done && (
                        <svg width="10" height="10" viewBox="0 0 10 10">
                          <polyline points="1.5,5 4,7.5 8.5,2.5" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </button>
                    <span className={`task-label ${t.done ? 'done' : ''}`}>{t.title}</span>
                    <button className="delete-btn" onClick={() => handleDelete(t.id)}>
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                        <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-header">
            <span className="section-title">Environment Info</span>
          </div>
          <div className="section-body">
            <div className="meta-grid">
              <div className="meta-item">
                <div className="meta-label">Environment</div>
                <div className="meta-value">{health?.env}</div>
              </div>
              <div className="meta-item">
                <div className="meta-label">Pull Request</div>
                <div className="meta-value">#{health?.pr}</div>
              </div>
              <div className="meta-item">
                <div className="meta-label">Database Status</div>
                <div className="meta-value" style={{ color: health?.db === 'connected' ? '#28c840' : '#ff5f57' }}>
                  {health?.db}
                </div>
              </div>
              <div className="meta-item">
                <div className="meta-label">Frontend</div>
                <div className="meta-value">React + Vite</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="window-footer">
        <span className="footer-text">API v{health?.version || '1.0'}</span>
        <span className="footer-text" style={{ color: 'var(--env-color)', fontWeight: 600 }}>Multi-Container Architecture Active</span>
      </div>
    </div>
  )
}

export default App
