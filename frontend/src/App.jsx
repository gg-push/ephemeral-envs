import { useEffect, useRef, useState } from 'react'

const Check = () => (
  <svg width="11" height="11" viewBox="0 0 10 10" aria-hidden="true">
    <polyline
      points="1.6,5.2 4,7.6 8.4,2.6"
      fill="none"
      stroke="#ffffff"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const Cross = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <path d="M2.5 2.5l7 7M9.5 2.5l-7 7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
)

async function fetchSnapshot() {
  const [tasksRes, healthRes] = await Promise.all([
    fetch('/api/tasks'),
    fetch('/api/health'),
  ])
  // /api/health returns 503 when Postgres is unreachable while still sending its
  // JSON payload, so we parse it either way.
  if (!tasksRes.ok && !healthRes.ok) {
    throw new Error('backend unreachable')
  }
  const health = await healthRes.json()
  const tasks = tasksRes.ok ? await tasksRes.json() : []
  return { health, tasks }
}

function App() {
  const [tasks, setTasks] = useState([])
  const [health, setHealth] = useState(null)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [copied, setCopied] = useState(false)
  const copyTimer = useRef(null)

  const prNumber = health?.pr ?? '0'
  const envName = health?.env ?? 'local'
  const commitSha = health?.version ?? 'dev'
  const parsedPr = Number.parseInt(prNumber, 10)
  // 137 is the golden angle so consecutive PR numbers get distinct hues.
  const hue = Number.isNaN(parsedPr) ? 210 : (parsedPr * 137) % 360

  useEffect(() => {
    document.documentElement.style.setProperty('--env-h', String(hue))
  }, [hue])

  useEffect(() => {
    if (health?.env) {
      document.title = `${health.env} preview`
    }
  }, [health])

  useEffect(() => {
    let cancelled = false
    fetchSnapshot()
      .then((data) => {
        if (cancelled) return
        setHealth(data.health)
        setTasks(data.tasks)
        setFailed(false)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      if (copyTimer.current) clearTimeout(copyTimer.current)
    }
  }, [])

  const retry = async () => {
    setLoading(true)
    try {
      const data = await fetchSnapshot()
      setHealth(data.health)
      setTasks(data.tasks)
      setFailed(false)
    } catch {
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }

  const copyCommit = async () => {
    try {
      await navigator.clipboard?.writeText(commitSha)
      setCopied(true)
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 1600)
    } catch {
      // Clipboard API can be blocked on non-HTTPS origins; ignore quietly.
    }
  }

  const add = async (event) => {
    event.preventDefault()
    const title = draft.trim()
    if (!title) return

    setDraft('')
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
    if (!res.ok) return
    const created = await res.json()
    setTasks((prev) => [...prev, created])
  }

  const toggle = async (id) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)))
    await fetch(`/api/tasks/${id}/toggle`, { method: 'POST' })
  }

  const remove = async (id) => {
    setTasks((prev) => prev.filter((t) => t.id !== id))
    await fetch(`/api/tasks/${id}`, { method: 'DELETE' })
  }

  if (loading) {
    return (
      <main className="desk">
        <div className="sheet sheet-state" role="status" aria-live="polite">
          <div className="spinner" />
          <p className="state-note">Connecting to preview environment</p>
        </div>
      </main>
    )
  }

  if (failed) {
    return (
      <main className="desk">
        <section className="sheet sheet-state">
          <div className="stamp-bar" aria-hidden="true" />
          <div className="state-body">
            <h1 className="state-title">Preview API is still starting up</h1>
            <p className="state-note">
              The frontend is ready, but <code>/api/health</code> has not answered yet. Wait a
              few seconds for Postgres and FastAPI to finish booting, then check again.
            </p>
            <button className="btn" type="button" onClick={retry}>
              Try again
            </button>
          </div>
        </section>
      </main>
    )
  }

  const dbOk = health?.db === 'connected'
  const doneCount = tasks.filter((t) => t.done).length

  return (
    <main className="desk">
      <article className="sheet">
        <div className="stamp-bar" aria-hidden="true" />

        <header className="sheet-head">
          <div className="head-top">
            <span className="env-tag">
              <span className="env-swatch" aria-hidden="true" />
              Pull request #{prNumber}
            </span>
            <button
              type="button"
              className="sha-btn"
              onClick={copyCommit}
              title="Copy commit SHA"
            >
              {copied ? 'Copied' : `Commit ${commitSha}`}
            </button>
          </div>

          <h1 className="env-name">{envName}</h1>

          <p className="env-meta">
            <span className="db-pill">
              <span className={`db-dot${dbOk ? '' : ' is-bad'}`} aria-hidden="true" />
              {dbOk ? 'Postgres connected' : 'Postgres unreachable'}
            </span>
            <span className="ns-note">Isolated namespace</span>
          </p>
        </header>

        <form className="compose" onSubmit={add}>
          <input
            className="input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add a review note..."
            aria-label="Add a review note"
          />
          <button className="btn" type="submit" disabled={!draft.trim()}>
            Add note
          </button>
        </form>

        <div className="list-bar">
          <h2 className="list-heading">Review checklist</h2>
          <span className="list-count">
            {doneCount} of {tasks.length} done
          </span>
        </div>

        {tasks.length === 0 ? (
          <p className="empty">Nothing logged yet. Add a quick check while reviewing this branch.</p>
        ) : (
          <ul className="tasks">
            {tasks.map((task) => {
              const isSystem = task.title.startsWith('[System]')
              return (
                <li
                  key={task.id}
                  className={[
                    'task',
                    task.done ? 'is-done' : '',
                    isSystem ? 'is-seed' : '',
                  ]
                    .join(' ')
                    .trim()}
                >
                  <button
                    type="button"
                    className={`check${task.done ? ' is-done' : ''}`}
                    onClick={() => toggle(task.id)}
                    aria-label={task.done ? 'Mark as not done' : 'Mark as done'}
                  >
                    {task.done && <Check />}
                  </button>
                  <span className="task-text">{task.title}</span>
                  <button
                    type="button"
                    className="remove"
                    onClick={() => remove(task.id)}
                    aria-label="Remove note"
                  >
                    <Cross />
                  </button>
                </li>
              )
            })}
          </ul>
        )}

        <footer className="sheet-foot">
          Isolated namespace with its own Postgres database. Removed automatically when this PR
          closes or sits idle for 48 hours.
        </footer>
      </article>
    </main>
  )
}

export default App
