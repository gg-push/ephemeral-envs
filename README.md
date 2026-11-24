# Ephemeral PR Preview Environments

[![CI](https://github.com/gg-push/ephemeral-envs/actions/workflows/ci.yml/badge.svg)](https://github.com/gg-push/ephemeral-envs/actions/workflows/ci.yml)

In most teams, developers fight over a single shared staging server. This project removes that bottleneck: **every open pull request automatically gets its own live, isolated full-stack environment** (React frontend + FastAPI backend + PostgreSQL 16 database + unique URL) inside Kubernetes, and deletes itself when the PR closes or goes idle.

---

## Lifecycle at a Glance

| Event | What Happens Automatically | Typical Time |
|---|---|---|
| **PR Opened** | CI builds immutable multi-arch images (`:<sha>`), spins up namespace `pr-<n>`, routes `http://pr-<n>.local.127.0.0.1.nip.io`, and comments the URL on the PR | ~90s |
| **New Commit Pushed** | CI builds new `:<sha>` images and updates only the running `pr-<n>` pods and sticky PR comment | ~60s |
| **PR Idle > 48 Hours** | Environment is automatically torn down to save cluster CPU/RAM; pushing a new commit brings it right back | ~60s |
| **PR Closed / Merged** | Namespace `pr-<n>` (pods, DB, ingress) is completely deleted and the sticky PR comment is marked removed | ~60s |

### Why Polling Instead of Webhooks?
Webhook-based preview pipelines break whenever a delivery fails or a local cluster is asleep when a PR closes, leaking namespaces forever. Here, an in-cluster controller simply asks GitHub every 60 seconds **"which PRs are currently open and active?"** and makes the cluster match that list — so GitHub Actions needs **zero cluster credentials or deploy scripts**.

---

## Architecture

![Ephemeral Preview Environments Architecture](./docs/architecture.svg)

**Two quick terms if you haven't used them:**
- **Kluctl (`kluctl.io`):** A pull-based Kubernetes GitOps deployer (similar to ArgoCD) with built-in Jinja2 templating (`{{ args.pr_number }}`), so per-PR namespaces don't need Kustomize patch hacks.
- **`nip.io`:** A free wildcard DNS service that resolves `*.127.0.0.1.nip.io` straight to `127.0.0.1`, giving every PR its own hostname locally without editing `/etc/hosts`.

---

## Security & Reliability Highlights

| Control | Implementation | Why It Matters |
|---|---|---|
| **Fork Guard** | `head: gg-push:.*` filter + CI repo check | Prevents external fork PRs from deploying code into your cluster |
| **Immutable Images** | Tagged by commit `<sha>` (`linux/amd64,arm64`) | Always know the exact commit running in `pr-42`; avoids mutable tag cache bugs |
| **Hardened Containers** | Non-root UIDs (`1000`/`101`/`70`), `readOnlyRootFilesystem`, `drop: ["ALL"]`, `RuntimeDefault` seccomp, `automountServiceAccountToken: false` | Minimal blast radius if an app container is compromised; HTML output is escaped against stored XSS |
| **Namespace Isolation** | `NetworkPolicy` (`env-isolation`) + `ResourceQuota` (`1 CPU`, `1 GiB`, `5 pods`) | Blocks cross-PR database access and stops one noisy PR from starving the cluster |
| **Least-Privilege RBAC** | `preview-templater` Role + `preview-deployer` ClusterRole | Controller can manage preview resources without holding `cluster-admin` or write access to pods/events |
| **Split Health Probes** | `/api/live` (process only) vs. `/api/health` (checks Postgres, returns `503`) | Prevents a slow database startup from triggering Kubernetes restart loops |

---

## Repository Layout

```text
ephemeral-envs/
├── .github/workflows/
│   ├── ci.yml                     # Python lint/tests, offline kluctl render + kubeconform, frontend build
│   ├── pr-preview.yml             # Multi-arch Buildx push to GHCR on PR open/sync
│   └── pr-closed.yml              # Updates sticky PR comment when closed (cluster cleanup is controller-driven)
├── app/                           # Hardened FastAPI backend + pytest suite
├── frontend/                      # React/Vite UI served by unprivileged Nginx (:8080)
├── deploy/                        # Kluctl templates: namespace, NetworkPolicy, postgres, backend, frontend, ingress
├── docs/architecture.svg          # Vector architecture diagram
├── gitops/
│   ├── rbac.yaml                  # Scoped ServiceAccounts & Roles
│   └── preview-generator.yaml     # Declarative PR polling, 48h TTL expiry, KluctlDeployment & sticky comments
├── .kluctl.yaml                   # Target definition & per-PR pruning discriminator
└── deployment.yaml                # Deployment ordering & common labels
```

---

## Quickstart: Run Locally ($0 via `k3d`)

Requires Docker, `k3d`, `kubectl`, and `kluctl`.

```bash
# 1. Create a local k3d cluster (Traefik ingress + metrics-server ship built-in)
k3d cluster create ephemeral-envs -p "80:80@loadbalancer" -p "443:443@loadbalancer"

# 2. Install Kluctl & Template Controllers
kluctl controller install
kubectl apply -f https://raw.githubusercontent.com/kluctl/template-controller/v0.9.4/deploy/manifests/template-controller.yaml

# 3. Apply least-privilege RBAC and a GitHub read/comment token
kubectl apply -f gitops/rbac.yaml
kubectl create secret generic github-credentials -n ephemeral-envs-system \
  --from-literal=token=<github_pat> \
  --from-literal=username=<github_user> \
  --from-literal=password=<github_pat>

# 4. Start the 60s PR reconciliation loop
kubectl apply -f gitops/preview-generator.yaml
```

*(Note: GHCR packages are public so preview namespaces can pull images without storing registry credentials inside Git.)*

### Testing Templates Locally Without a Cluster

```bash
kluctl render -t preview --offline-kubernetes -a pr_number=42 -a image_tag=<sha> --print-all
kluctl diff   -t preview -a pr_number=42 -a image_tag=<sha>
```

---

## Local Laptop vs. Production Cluster

| Component | Local (`k3d` on Laptop) | Production Cluster |
|---|---|---|
| **Domain** | `*.local.127.0.0.1.nip.io` | Wildcard `*.preview.example.com` DNS A-record |
| **TLS** | Plain HTTP `:80` | `cert-manager` DNS-01 wildcard cert (avoids Let's Encrypt rate limits & CT-log branch leaks) |
| **Access Control** | Bound to `127.0.0.1` | `oauth2-proxy` Traefik middleware (GitHub OAuth SSO, no per-PR passwords) |
| **Observability** | `kubectl top pod -n pr-42` / `k9s` | Prometheus + Grafana scraping `/metrics` |
