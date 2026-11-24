# Deploying on a Production Server with a Custom Domain

This guide adapts the local `k3d` setup to a Linux VPS (`k3s`) with a real domain (`*.preview.example.com`), wildcard TLS via `cert-manager`, and GitHub OAuth authentication via `oauth2-proxy`.

---

## 1. Server, Firewall & Wildcard DNS

1. Point a wildcard DNS `A` record at your server's public IP:
   ```text
   *.preview.example.com  →  <SERVER_PUBLIC_IP>
   ```
2. Lock down the host firewall (`ufw`) before exposing the cluster:
   ```bash
   sudo ufw default deny incoming
   sudo ufw allow OpenSSH
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
3. Install single-node `k3s` (includes Traefik and `metrics-server` out of the box):
   ```bash
   curl -sfL https://get.k3s.io | sh -
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   ```

---

## 2. Install Controllers, RBAC & GitHub Credentials

```bash
# 1. Kluctl & Template Controllers
kluctl controller install
kubectl apply -f https://raw.githubusercontent.com/kluctl/template-controller/v0.9.4/deploy/manifests/template-controller.yaml

# 2. Least-privilege RBAC & GitHub token (repo read + PR comment write)
kubectl apply -f gitops/rbac.yaml
kubectl create secret generic github-credentials -n ephemeral-envs-system \
  --from-literal=token=<github_pat> \
  --from-literal=username=<github_user> \
  --from-literal=password=<github_pat>
```

---

## 3. Configure Your Domain (`preview.example.com`)

Replace `local.127.0.0.1.nip.io` with `preview.example.com` in three files:
1. [`.kluctl.yaml`](../.kluctl.yaml) — `base_domain` default (`preview.example.com`).
2. [`gitops/preview-generator.yaml`](../gitops/preview-generator.yaml) — the `**URL**` line in the `GithubComment` body (`https://pr-{{ matrix.pr.number }}.preview.example.com`).
3. [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — the `grep -q "host: ..."` assertion in `manifests`.

Then start the reconciliation loop:

```bash
kubectl apply -f gitops/preview-generator.yaml
```

---

## 4. Wildcard HTTPS (`cert-manager` DNS-01 + Traefik `TLSStore`)

Using a **single DNS-01 wildcard certificate** (`*.preview.example.com`) avoids Let's Encrypt per-domain rate limits and prevents PR numbers/branch names from leaking into public Certificate Transparency (CT) logs.

1. Install `cert-manager`:
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.17.1/cert-manager.yaml
   ```
2. Create a DNS-01 `ClusterIssuer`, wildcard `Certificate` in `kube-system` (where k3s runs Traefik), and Traefik default `TLSStore` so every preview `Ingress` serves TLS automatically without copying Secrets into every `pr-*` namespace:
   ```yaml
   apiVersion: cert-manager.io/v1
   kind: ClusterIssuer
   metadata:
     name: letsencrypt-dns
   spec:
     acme:
       server: https://acme-v02.api.letsencrypt.directory/directory
       email: ops@example.com
       privateKeySecretRef:
         name: letsencrypt-dns-key
       solvers:
         - dns01:
             cloudflare:
               apiTokenSecretRef:
                 name: cloudflare-api-token
                 key: api-token
   ---
   apiVersion: cert-manager.io/v1
   kind: Certificate
   metadata:
     name: preview-wildcard-tls
     namespace: kube-system
   spec:
     secretName: preview-wildcard-tls
     issuerRef:
       name: letsencrypt-dns
       kind: ClusterIssuer
     dnsNames:
       - "*.preview.example.com"
   ---
   apiVersion: traefik.io/v1alpha1
   kind: TLSStore
   metadata:
     name: default
     namespace: kube-system
   spec:
     defaultCertificate:
       secretName: preview-wildcard-tls
   ```
3. In [`deploy/ingress/ingress.yaml`](../deploy/ingress/ingress.yaml), enforce HTTPS and reference `tls:` for the host:
   ```yaml
   metadata:
     annotations:
       traefik.ingress.kubernetes.io/router.entrypoints: websecure
       traefik.ingress.kubernetes.io/router.tls: "true"
   spec:
     tls:
       - hosts:
           - "pr-{{ args.pr_number }}.{{ args.base_domain }}"
   ```

---

## 5. Protect Preview URLs with GitHub OAuth (`oauth2-proxy`)

Publicly reachable preview URLs should require team authentication rather than sitting open on the internet. Deploy one shared `oauth2-proxy` instance in `kube-system` (configured with `--cookie-domain=.preview.example.com` and `--github-org=<your-org>`) and attach a Traefik `Middleware` to every preview Ingress:

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: github-auth
  namespace: kube-system
spec:
  forwardAuth:
    address: http://oauth2-proxy.kube-system.svc.cluster.local:4180/
    trustForwardHeader: true
    authResponseHeaders:
      - X-Auth-Request-User
      - X-Auth-Request-Email
```

Then add the middleware annotation to [`deploy/ingress/ingress.yaml`](../deploy/ingress/ingress.yaml):

```yaml
metadata:
  annotations:
    traefik.ingress.kubernetes.io/router.middlewares: kube-system-github-auth@kubernetescrd
```

### Additional Production Notes
- **Private GHCR Images:** If you make GHCR packages private, create a registry pull Secret per `pr-*` namespace via `deploy/` (using a cluster secret sync tool such as External Secrets Operator rather than committing credentials to Git) and add `imagePullSecrets` to the backend/frontend Deployments.
- **Monitoring:** Backend pods already expose `/metrics` (`prometheus.io/scrape: "true"` annotations are present on `devboard-app`), ready for Prometheus scraping.
