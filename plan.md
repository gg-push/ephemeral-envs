# Ephemeral Dev Environments — Detailed Project Plan

## What This Project Does

Every open pull request on GitHub has its own isolated, live environment.
Not "a PR opening triggers a deploy" — the cluster continuously makes the set of
running environments match the set of open pull requests.
No shared staging. No "works on my machine."

---

## Full Architecture (pull-based)

The key inversion: **nothing reacts to a pull request closing.** A controller
inside the cluster asks GitHub what is open and converges on the answer, so
there is no event that can be missed.

```
GitHub Actions (self-hosted)          In-cluster controllers
      │                                        │
      │ builds images only                     │ every 1 minute:
      │ NO cluster credentials                 │
      ▼                                        ▼
Local registry  ◄─── kubelet pulls ───  ListGithubPullRequests
(k3d-registry:5000)                     "which PRs are open?"
                                               │
                                               ▼
                                        ObjectTemplate
                                        one output per open PR
                                               │
                                               ▼
                                        KluctlDeployment: pr-42
                                               │
                                               ▼
                                        Namespace pr-42
                                        ├── Frontend      (React)
                                        ├── Backend       (FastAPI)
                                        ├── PostgreSQL    (per env)
                                        ├── ResourceQuota
                                        └── Ingress → pr-42.local.127.0.0.1.nip.io

PR closed / merged
      │
      ▼
It leaves ListGithubPullRequests → the matrix input disappears →
the KluctlDeployment is pruned → the namespace goes with it.

No cleanup code exists. Teardown is a property of the system.
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

### 3. Ingress Controller — Traefik

- Ships with K3d by default, so there is nothing extra to install.
- Routes `pr-42.*.nip.io` → correct K8s service in `pr-42` namespace.
- Also provides the `Middleware` CRD used for per-environment Basic Auth.
- K3d allows exposing port 80/443 directly to localhost.

### 4. Container Images — Built Locally, No Registry

- Originally planned to push to GHCR, but the runner and the cluster are on the
  same machine, so a registry round-trip buys nothing.
- GitHub Actions builds the image and `k3d image import` loads it straight into
  the cluster nodes.
- Images are tagged `ephemeral-envs-{backend,frontend}:pr-<number>` and removed
  by the cleanup workflow when the PR closes.

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

### 7. kluctl (replaced Kustomize overlays)

- The deployment project (`.kluctl.yaml` + `deployment.yaml` + `deploy/`) is the
  single definition of an environment.
- Per-PR values are plain Jinja2 in the manifests (`{{ args.pr_number }}`), so
  there are no generated overlays and no JSON patches to keep in sync.
- The *same* project deploys from the CLI and from the controller, so
  `kluctl diff -t preview -a pr_number=42` shows exactly what GitOps will do.
- `discriminator` gives each environment its own pruning identity.

### 8. GitOps controllers

- **kluctl controller** — reconciles `KluctlDeployment` objects in-cluster.
- **template-controller** — `ListGithubPullRequests` + `ObjectTemplate` generate
  one `KluctlDeployment` per open PR and prune it when the PR closes.

### 9. Local container registry

- Pull-based delivery means the cluster fetches its own images, so
  `k3d image import` is no longer sufficient.
- A k3d-managed registry keeps everything local and fast while still being a
  real registry the kubelet can pull from.

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
- [x] Add a frontend service container (e.g., React, Next.js, or Vue)
- [x] Update Traefik Ingress to route `/api/*` to Python backend and `/*` to Frontend
- [x] Configure frontend to dynamically point to the correct backend API URL

### Phase 8: Ephemeral Observability Dashboard
- [x] Deploy global Grafana/Prometheus stack to the cluster
- [x] Automatically generate and inject PR-specific metrics dashboard URL into GitHub comment
- [x] Configure dashboards to track CPU, memory, and API latency for the specific `pr-*` namespace

### Phase 9: Central Developer Portal — built, then removed
- [x] Build a lightweight "Control Panel" web app deployed in the `default` namespace
- [x] Configure app to read Kubernetes API and list all active `pr-*` namespaces
- [x] Provide one-click clickable links to all live preview environments on the cluster
- [x] **Removed in Phase 11.** The PR comment already carries the environment URL,
      and a reviewer is on the PR anyway — the same interface Vercel and Netlify
      use. `kubectl get ns` and `kluctl webui` cover the operator view. Keeping a
      dashboard that string-parsed namespace names and could not see failed
      deployments would have cost more than it returned.

### Phase 10: Hardening
- [x] Refuse to run the self-hosted workflows for fork PRs
- [x] Add a `concurrency` group so two pushes cannot race on one namespace
- [x] Mask generated passwords in logs; reuse them across pushes to one PR
- [x] Stamp namespaces with `pr-number`, `pr-author`, `git-sha` and `expires-at`
- [x] Replace the TTL CronJob with a reconciler that converges on GitHub state
- [x] Add liveness/readiness/startup probes and a DB-independent `/api/live`
- [x] Return 503 from `/api/health` when the database is unreachable
- [x] Wait for Postgres on boot instead of crash-looping
- [x] Add a post-deploy smoke test that exercises the real ingress URL
- [x] Collapse per-push PR comments into one sticky comment
- [x] Add `ci.yml`: ruff, pytest, and kubeconform on GitHub-hosted runners
- [x] Add tests for the app and for the namespace-deletion logic
- [x] Delete the unused docker-compose dev stack

### Phase 11: Migration to GitOps (kluctl) — slice 1

Evaluated ArgoCD, Flux and kluctl first. Flux has no pull-request generator, so
the dynamic part would have been mine to maintain. ArgoCD's `ApplicationSet` PR
generator fits well but threads per-PR values through awkward kustomize patches
and is heavy on a laptop. kluctl has the same generator concept plus native
templating and a CLI that drives the identical project.

- [x] Convert the manifests into a kluctl deployment project (`deploy/`)
- [x] Drop `namePrefix` entirely — namespace isolation makes resource names
      constant, so `DATABASE_URL` no longer needs per-PR rewriting
- [x] Add a per-PR `discriminator` so pruning cannot cross environments
- [x] `ListGithubPullRequests` + `ObjectTemplate` generate one deployment per PR
- [x] Scoped RBAC: the deployer cannot touch anything outside a preview env
- [x] Move to a local k3d registry so the cluster pulls its own images
- [x] Tag images with the head SHA instead of a mutable `pr-N` tag
- [x] Strip all cluster credentials out of GitHub Actions
- [x] Replace the smoke test with a convergence check that asserts the deployed
      version matches the pushed commit
- [x] `deployInterval: 5m` for drift correction
- [x] CI renders the project offline and asserts the templated values, so a
      Jinja2 typo fails loudly instead of rendering an empty string
- [x] Retire the reconciler CronJob — `ObjectTemplate` pruning supersedes it
- [x] Retire `pr-deploy.yml` / `pr-cleanup.yml`
- [x] Remove the Control Panel (see Phase 9)

### Phase 12: Restoring what slice 1 dropped

- [ ] Basic Auth per environment. A generated password cannot be committed, so
      this needs either Sealed Secrets, a kluctl hook that generates credentials
      in-cluster, or an operator. Decide which before rebuilding it.
- [ ] TTL for pull requests that stay open for weeks. Closed PRs are handled;
      long-lived ones currently keep their environment forever.
- [ ] Bring `monitoring/` under GitOps too, so the entire cluster state lives
      in Git.

### Phase 13: Later

- [ ] Record a demo GIF or video for portfolio
- [ ] Post the preview URL with the template-controller's `GithubComment` CRD
      instead of a GitHub Actions step
- [ ] Alembic migrations as an initContainer, replacing the duplicated schema in
      `seed.sql` and `Base.metadata.create_all`
- [ ] KEDA scale-to-zero for idle environments
- [ ] Commit a lockfile for `frontend/` so its image builds reproducibly
- [ ] LocalStack for mocking AWS dependencies per PR (was Phase 6)
- [ ] Run it on a real cloud cluster with proper DNS and TLS

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

> "Built a self-hosted ephemeral preview-environment platform on Kubernetes: every open pull
> request has an isolated namespace with its own React frontend, FastAPI backend, PostgreSQL
> database and URL. Implemented it as pull-based GitOps with kluctl — an in-cluster controller
> continuously reconciles running environments against the set of open PRs, so teardown is a
> property of the system rather than a webhook that can be missed, and CI holds no cluster
> credentials at all. Evaluated ArgoCD and Flux against kluctl before choosing.
> K3d, kluctl, Traefik, Prometheus/Grafana, GitHub Actions."

The second sentence is the one that matters. "Reconciliation instead of an event
handler" and "CI holds no cluster credentials" are the two claims that separate
this from a tutorial project — lead with them in interviews.
