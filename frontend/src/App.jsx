import { useCallback, useEffect, useState } from 'react'

const Check = () => (
  <svg width="11" height="11" viewBox="0 0 10 10" aria-hidden="true">
    <polyline
      points="1.5,5.2 3.9,7.6 8.5,2.6"
      fill="none"
      stroke="hsl(225 20% 8%)"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const Cross = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <path
      d="M2 2l8 8M10 2l-8 8"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    />
  </svg>
)

function App() {
  const [tasks, setTasks] = useState([])
  const [health, setHealth] = useState(null)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  // Every environment gets its own hue, so which preview you are looking at is
  // obvious at a glance rather than something you read out of the URL bar.
  const prNumber = health?.pr ?? '0'
  const hue = (Number.parseInt(prNumber, 10) * 47) % 360

  useEffect(() => {
    document.documentElement.style.setProperty('--env-h', Number.isNaN(hue) ? 210 : hue)
  }, [hue])

  const load = useCallback(async () => {
    try {
      const [tasksRes, healthRes] = await Promise.all([
        fetch('/api/tasks'),
        fetch('/api/health'),
      ])
      // /api/health answers 503 when the database is unreachable, and still
      // returns a useful body, so it is read either way.
      if (!tasksRes.ok && !healthRes.ok) throw new Error('backend unreachable')

      setHealth(await healthRes.json())
      setTasks(tasksRes.ok ? await tasksRes.json() : [])
      setFailed(false)
    } catch {
      setFailed(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

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

  const shell = (body) => (
    <div className="window">
      <div className="titlebar">
        <div className="traffic">
          <span className="dot dot-red" />
          <span className="dot dot-yellow" />
          <span className="dot dot-green" />
        </div>
        <div className="titlebar-title">devboard</div>
      </div>
      {body}
    </div>
  )

  if (loading) {
    return shell(
      <div className="centred">
        <div className="spinner" />
      </div>,
    )
  }

  if (failed) {
    return shell(
      <div className="centred">
        <div className="fail-title">Backend unreachable</div>
        <p className="fail-note">
          The frontend is up but <code>/api</code> did not answer. The environment is
          probably still rolling out.
        </p>
      </div>,
    )
  }

  const dbOk = health?.db === 'connected'
  const done = tasks.filter((t) => t.done).length

  return shell(
    <>
      <div className="content">
        <section className="env">
          <div className="env-label">
            <span className="env-beacon" />
            Preview environment
          </div>
          <div className="env-name">{health?.env ?? 'local'}</div>
          <div className="env-facts">
            <span className="fact">
              <span className={`status-dot${dbOk ? '' : ' is-bad'}`} />
              {dbOk ? 'own database' : 'database unreachable'}
            </span>
            <span className="fact">commit {health?.version ?? 'dev'}</span>
          </div>
        </section>

        <form className="compose" onSubmit={add}>
          <input
            className="input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="What needs doing?"
            aria-label="New task"
          />
          <button className="btn" type="submit" disabled={!draft.trim()}>
            Add
          </button>
        </form>

        <section className="panel">
          <header className="panel-head">
            <span className="panel-title">Tasks</span>
            <span className="badge">{done}/{tasks.length}</span>
          </header>

          {tasks.length === 0 ? (
            <div className="empty">Nothing here yet</div>
          ) : (
            <ul className="tasks">
              {tasks.map((task) => (
                <li
                  key={task.id}
                  className={[
                    'task',
                    task.done ? 'is-done' : '',
                    task.title.startsWith('[System]') ? 'is-seed' : '',
                  ].join(' ').trim()}
                >
                  <button
                    className={`check${task.done ? ' is-done' : ''}`}
                    onClick={() => toggle(task.id)}
                    aria-label={task.done ? 'Mark as not done' : 'Mark as done'}
                  >
                    {task.done && <Check />}
                  </button>
                  <span className="task-text">{task.title}</span>
                  <button
                    className="remove"
                    onClick={() => remove(task.id)}
                    aria-label="Delete task"
                  >
                    <Cross />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <footer className="footer">
        <span>Isolated Postgres · torn down with the pull request</span>
        <a href="/api/health">health</a>
      </footer>
    </>,
  )
}

export default App
