# Developer Control Panel

The Control Panel is a centralized, minimalist web dashboard that reads the Kubernetes API to display all active Ephemeral Preview Environments (Pull Requests). 

It consists of:
1. **Frontend**: A React SPA (Vite) styled with professional, Vercel-inspired minimalism.
2. **Backend**: A tiny Python FastAPI service that securely queries the K3d cluster's namespaces and ingresses using a Kubernetes ServiceAccount.

## Architecture

- The application is deployed into the `default` namespace.
- It uses a custom `ServiceAccount` and `ClusterRoleBinding` to gain read-only access to cluster namespaces, deployments, and ingresses.
- The Ingress controller routes traffic for `control.local.127.0.0.1.nip.io` to the React frontend, and `/api` to the Python backend.

---

## How to Build and Deploy (Locally)

Because this is a permanent developer tool (unlike the ephemeral pull requests), it is deployed directly to the K3d cluster. Run these commands from the root of this `control-panel` directory.

### 1. Build and Import the Backend
```bash
cd backend
docker build -t control-panel-backend:latest .
k3d image import control-panel-backend:latest -c ephemeral-envs
cd ..
```

### 2. Build and Import the Frontend
```bash
cd frontend
docker build -t control-panel-frontend:latest .
k3d image import control-panel-frontend:latest -c ephemeral-envs
cd ..
```

### 3. Deploy to Kubernetes
Apply the Kubernetes manifests using Kustomize:
```bash
kubectl apply -k k8s/
```

### 4. Access the Dashboard
Once the pods are running, the Control Panel will be instantly available at:
👉 **[http://control.local.127.0.0.1.nip.io](http://control.local.127.0.0.1.nip.io)**
