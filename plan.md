# Ephemeral Dev Environments — Detailed Project Plan

## What This Project Does

Every pull request on GitHub automatically gets its own isolated, live environment.
Dev opens PR → Environment spins up → Unique URL generated → PR closes → Environment dies.
No shared staging. No "works on my machine." Pure automation.

---

## Full Architecture

```
GitHub PR Opened
      │
      ▼
GitHub Actions Workflow (GitHub-hosted runner)
      │
      ▼
Self-Hosted Runner (on YOUR laptop) ◄── Needed to reach local K3s
      │
      ▼
K3s Cluster (Local Kubernetes on laptop)
      │
      ├── Create Namespace    (pr-{number})
      ├── Deploy App          (Helm release)
      ├── Deploy PostgreSQL   (Helm subchart, per namespace)
      └── Create Ingress      (pr-{number}.{YOUR_IP}.nip.io)
      │
      ▼
Post PR comment: "✅ Environment ready → http://pr-42.10.0.0.1.nip.io"
      │
PR Closed / Merged
      │
      ▼
GitHub Actions Cleanup Workflow
      │
      ▼
Helm uninstall + Delete namespace → Everything destroyed
```

---

## What You Need

### 1. Kubernetes Cluster — K3d (Local)

- K3d runs K3s inside Docker containers.
- Runs fine on a laptop. Fast startup and clean teardown.
- Install: `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`

### 2. Domain / DNS — nip.io (Free, Zero Setup)

- **No domain purchase needed.**
- `nip.io` is a magic free DNS service.
- Any IP becomes a wildcard domain automatically.
- Example: `pr-42.192.168.1.100.nip.io` → resolves to `192.168.1.100`
- Your Ingress controller handles routing from IP to the correct namespace.

### 3. Ingress Controller — Nginx

- Routes `pr-42.*.nip.io` → correct K8s service in `pr-42` namespace.
- K3d allows exposing port 80/443 directly to localhost.

### 4. Container Registry — GitHub Container Registry (GHCR)

- Free. Built into GitHub.
- GitHub Actions builds Docker image → pushes to `ghcr.io/yourusername/app`
- K3d pulls image from GHCR on every deploy.

### 5. Self-Hosted GitHub Actions Runner (Critical)

- GitHub's cloud runners CANNOT reach your local K3d cluster.
- You run a small agent on your laptop.
- It listens for GitHub Actions jobs and executes them locally.
- Has full access to your K3d cluster.
- Setup: Download from GitHub repo Settings → Actions → Runners.

### 6. Sample Web App (To Deploy)

- Python FastAPI application.
- Minimal macOS inspired UI, task list, and Swagger docs.
- Has a `Dockerfile`.
- Has a Kustomize configuration for Kubernetes deployment.

### 7. Kustomize

- Built into Kubernetes (`kubectl apply -k`).
- Uses pure YAML and overlays (patches) instead of complex templating.
- We will dynamically inject PR numbers via `envsubst` during deployment.

---

## Phases

### Phase 1: Local Cluster Setup (SKIPPED for now)

- [x] Install k3d
- [ ] Create cluster: `k3d cluster create ephemeral-envs -p "80:80@loadbalancer"`
- [ ] Verify cluster: `kubectl get nodes`

### Phase 2: Sample App

- [x] Write Python FastAPI app
- [x] Write `Dockerfile`
- [x] Push image to GHCR manually first to test (SKIPPED for now)
- [x] Write Kustomize configuration:
  - `k8s/base/deployment.yaml`
  - `k8s/base/service.yaml`
  - `k8s/base/ingress.yaml`
  - `k8s/base/postgres.yaml` (Deploying Postgres directly)
  - `k8s/base/kustomization.yaml`
- [x] Test manual deploy: `kubectl apply -k ./k8s/base` (SKIPPED for now)
- [x] Verify app at `pr-1.127.0.0.1.nip.io` (SKIPPED for now)

### Phase 3: Self-Hosted Runner

- [ ] Register self-hosted runner in GitHub repo settings
- [ ] Run the runner agent on laptop (runs as a background service)

### Phase 3: CI/CD Pipeline (GitHub Actions)
- [x] Create `.github/workflows/pr-deploy.yml` (trigger on PR open/sync)
- [x] Create `.github/workflows/pr-cleanup.yml` (trigger on PR close)
- [x] Bash script logic to dynamically generate Kustomize overlays using `$PR_NUMBER`
- [x] Setup self-hosted runner (so Actions can access local K3d)

### Phase 4: Testing & E2E Validation
- [x] Test: Open a real PR → Watch environment appear → Test UI/DB
- [x] Test: Close PR → Watch `pr-cleanup.yml` destroy the namespace

### Phase 5: Polish

- [x] Add `ResourceQuota` per namespace (CPU: 500m, RAM: 512Mi limit)
- [x] Add TTL CronJob: auto-delete environments older than 24 hours
- [x] Write README with architecture diagram (use Mermaid or draw.io)
- [ ] Record a demo GIF or video for portfolio

### Phase 6: Advanced Enterprise Features (Optional)

- [x] Implement Web-Scraper Protection (Basic Auth via Ingress annotations)
- [ ] Phase 6: Cloud Dependency Mocking (LocalStack)
- [ ] Add LocalStack to the Kustomize deployment to mock AWS S3/SQS
- [ ] Update Python app to interact with the mocked S3 bucket
- [ ] Ensure full isolation of LocalStack data per PR

### Phase 7: Full-Stack Multi-Container Architecture
- [ ] Add a frontend service container (e.g., React, Next.js, or Vue)
- [ ] Update Traefik Ingress to route `/api/*` to Python backend and `/*` to Frontend
- [ ] Configure frontend to dynamically point to the correct backend API URL

### Phase 8: Ephemeral Observability Dashboard
- [ ] Deploy global Grafana/Prometheus stack to the cluster
- [ ] Automatically generate and inject PR-specific metrics dashboard URL into GitHub comment
- [ ] Configure dashboards to track CPU, memory, and API latency for the specific `pr-*` namespace

### Phase 9: Central Developer Portal
- [ ] Build a lightweight "Control Panel" web app deployed in the `default` namespace
- [ ] Configure app to read Kubernetes API and list all active `pr-*` namespaces
- [ ] Provide one-click clickable links to all live preview environments on the cluster

---

## Cost Breakdown

| Resource                     | Cost   |
| ---------------------------- | ------ |
| K3s on laptop                | $0     |
| nip.io DNS                   | $0     |
| GHCR (container registry)    | $0     |
| GitHub Actions (self-hosted) | $0     |
| GitHub repo                  | $0     |
| **Total**                    | **$0** |

---

## Expected Time: 4-5 Days

---

## CV Description (After Completion)

> "Built a self-hosted Ephemeral Preview Environment system using K3d, Kustomize, and GitHub Actions.
> Automatically provisions isolated Kubernetes namespaces per pull request with a unique nip.io URL,
> deploys a containerized Python FastAPI app with a dedicated PostgreSQL database per environment,
> and destroys all resources on PR close. Added namespace resource quotas and TTL-based auto-cleanup."
