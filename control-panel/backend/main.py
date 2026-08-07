from fastapi import FastAPI
from kubernetes import client, config
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Kubernetes configuration
try:
    # Works when running inside the cluster
    config.load_incluster_config()
except:
    try:
        # Works when running locally
        config.load_kube_config()
    except:
        pass

v1 = client.CoreV1Api()
networking_v1 = client.NetworkingV1Api()
apps_v1 = client.AppsV1Api()

@app.get("/api/environments")
def get_environments():
    envs = []
    try:
        namespaces = v1.list_namespace()
        for ns in namespaces.items:
            if ns.metadata.name.startswith("pr-"):
                name = ns.metadata.name
                
                # Find the ingress for this namespace to get the URL
                url = ""
                try:
                    ingresses = networking_v1.list_namespaced_ingress(name)
                    if ingresses.items:
                        url = f"http://{ingresses.items[0].spec.rules[0].host}"
                except Exception:
                    pass
                    
                # Find deployment status
                status = "Unknown"
                try:
                    deps = apps_v1.list_namespaced_deployment(name)
                    ready = True
                    if not deps.items:
                        ready = False
                    for dep in deps.items:
                        if dep.status.ready_replicas != dep.status.replicas:
                            ready = False
                            break
                    status = "Ready" if ready else "Deploying"
                except Exception:
                    pass

                envs.append({
                    "id": name,
                    "name": f"Pull Request #{name.split('-')[1]}",
                    "url": url,
                    "status": status,
                    "created_at": ns.metadata.creation_timestamp
                })
    except Exception as e:
        print(f"Error querying kubernetes: {e}")
        
    # Sort by PR number descending
    envs.sort(key=lambda x: int(x['id'].split('-')[1]) if len(x['id'].split('-')) > 1 and x['id'].split('-')[1].isdigit() else 0, reverse=True)
    return {"environments": envs}

@app.get("/api/health")
def health():
    return {"status": "ok"}
