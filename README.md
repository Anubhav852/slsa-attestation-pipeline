# SLSA-Attested, Hardened Kubernetes Workload

A small Flask service packaged as a shell-less, non-root container, deployed to Kubernetes with a locked-down `securityContext`, and built by a CI pipeline that signs the image and generates SLSA provenance. A built-in live console lets you attack the running container and watch Kubernetes recover from failures.

## Live demo

| Link | What it runs | Availability |
|---|---|---|
| https://requirements-speaks-tba-walnut.trycloudflare.com | The real 2-replica Kubernetes cluster (kind), exposed through a Cloudflare quick tunnel | Only while the author's laptop and tunnel are running |
| https://slsa-attestation-pipeline.onrender.com | The same Docker image on Render, as a single instance | Always on, but sleeps after 15 minutes idle; the first request can take 30 to 60 seconds |

The two links run the same image but different runtimes, so the security results differ. That difference is intentional and is explained below.

## How to test it

Open either link. Every result on the page comes from the running container or from the GitHub API at the moment you click. Nothing is pre-loaded.

1. **Who answered this request.** The page polls `/api/whoami` every second. On the cluster link, watch two pod names appear with their own request counters. That is the Kubernetes Service balancing requests across replicas.
2. **Attack the running container.** Press **Run all five**, or press each button on its own. The container really attempts each action and reports the result:
   - *Spawn a shell*: tries to execute `sh`, `bash`, `dash` and `rbash`.
   - *Find download tools*: looks for `curl` and `wget`.
   - *Write to filesystem*: tries to create a file in `/etc`, `/app` and `/tmp`.
   - *Escalate to root*: calls `setuid(0)` and tries to read `/etc/shadow`.
   - *Inspect privileges*: reads `/proc/self/status` for the UID, capability sets, `NoNewPrivs` and seccomp mode.
3. **Self-healing.**
   - *Crash the pod serving me* makes the process exit. Kubernetes restarts the container while the other replica keeps answering, and the timeline records the failure and the recovery.
   - *Copy kubectl delete command* copies `kubectl delete pod <name>` for the pod currently serving you. Run it in a terminal and watch the page stay up while a replacement pod starts.
4. **Supply chain.** The page fetches the latest GitHub Actions runs and the jobs of the newest run (signing and SLSA provenance) directly from the GitHub API.

Each attack also writes a JSON log line. To see them on the cluster:

```
kubectl logs -l app=secure-api --tail=20
```

### Expected results

| Check | Kubernetes cluster | Render |
|---|---|---|
| Spawn a shell | blocked | blocked |
| Find download tools | blocked | blocked |
| Escalate to root | blocked | blocked |
| Inspect privileges | uid 10001, `CapEff=0`, `CapBnd=0`, `NoNewPrivs=1`, `Seccomp=2` | uid 10001, `CapEff=0`, `NoNewPrivs=1`, non-empty `CapBnd`, `Seccomp=0` |
| Write to filesystem | blocked in `/etc`, `/app` and `/tmp` (read-only file system) | `/etc` denied, `/app` and `/tmp` writable |
| Pods shown | 2 | 1 |

The shell, download-tool and non-root results come from the **image**. The read-only filesystem, empty capability bounding set and seccomp profile come from the **Kubernetes manifest**, which Render does not apply. If a test ever shows "NOT blocked", that is a genuine finding about the environment, because the tests report what actually happened.

## How it works

```
git push -> GitHub Actions -> build image -> push to GHCR -> cosign keyless sign
                                                          -> SLSA container provenance
Dockerfile -> shell-less non-root image -> Deployment (2 replicas, hardened) -> NodePort Service
Browser -> console (static page) -> Flask API inside the container
```

### Container (`Dockerfile`)

- Multi-stage build on `python:3.11-slim`. Dependencies are installed in a builder stage, and the runtime stage contains only the app and its packages.
- Runs as unprivileged UID/GID `10001`.
- Removes `sh`, `bash`, `dash`, `rbash`, `curl` and `wget` from the runtime image.
- Note: this is a slim image with shells removed, not a distroless image.

### Kubernetes (`deployment.yaml`)

| Setting | Purpose |
|---|---|
| `runAsNonRoot`, `runAsUser/Group: 10001` | No root inside the container |
| `allowPrivilegeEscalation: false` | Sets `no_new_privs`, so child processes cannot gain rights |
| `readOnlyRootFilesystem: true` | Blocks file injection and runtime mutation |
| `capabilities.drop: ["ALL"]` | Removes all Linux capabilities |
| `seccompProfile: RuntimeDefault` | Filters dangerous system calls |
| `automountServiceAccountToken: false` | The pod gets no Kubernetes API credentials |
| Resource requests and limits | Bounds CPU and memory |
| 2 replicas, liveness and readiness probes on `/health` | Availability and self-healing |
| NodePort Service on 30080 | Load-balanced access to the pods |

### Live console (`app/app.py`, `app/static/index.html`)

| Endpoint | Purpose |
|---|---|
| `GET /` | The console page |
| `GET /health` | Probe endpoint |
| `GET /api/whoami` | Pod name, UID, uptime, requests served, image reference |
| `POST /api/attack/<name>` | Runs one of the five attack tests and returns the real outcome |
| `POST /api/chaos/crash` | Exits the process so you can watch recovery |

Responses send `Connection: close`, so each request opens a new connection and the Service balances it across pods.

### CI pipeline (`.github/workflows/`)

1. Builds the image and pushes it to GitHub Container Registry.
2. Signs the image digest with Sigstore cosign using keyless OIDC identity.
3. Calls the `slsa-github-generator` container workflow to produce SLSA provenance for the same digest.

To verify the published image yourself, take the digest from the latest successful run or from the package page, then:

```
cosign verify ghcr.io/anubhav852/slsa-attestation-pipeline@sha256:<DIGEST> \
  --certificate-identity-regexp "^https://github.com/Anubhav852/slsa-attestation-pipeline/" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

slsa-verifier verify-image ghcr.io/anubhav852/slsa-attestation-pipeline@sha256:<DIGEST> \
  --source-uri github.com/Anubhav852/slsa-attestation-pipeline
```

## Run it locally

Prerequisites: Docker Desktop, `kubectl`, and `kind`.

```
git clone https://github.com/Anubhav852/slsa-attestation-pipeline
cd slsa-attestation-pipeline
kind create cluster --config kind-config.yaml
docker build -t slsa-app:local .
kind load docker-image slsa-app:local
kubectl apply -f deployment.yaml
kubectl get pods
```

When both pods are `1/1 Running`, open http://localhost:30080.

After changing code, rebuild and reload the image, then restart the pods:

```
docker build -t slsa-app:local .
kind load docker-image slsa-app:local
kubectl rollout restart deployment slsa-hardened-app
```

To expose the local cluster publicly with a temporary Cloudflare quick tunnel:

```
cloudflared tunnel --url http://localhost:30080
```

## Known limitations

- The cluster in the demo runs a locally built image (`slsa-app:local`), not the GHCR image that CI signed. The console labels it as tag-only, not digest-pinned. To close the loop, deploy the GHCR image by digest after verifying it with the commands above.
- The Flask built-in server is used to keep the container write-free for the read-only filesystem demo. A production deployment would use a dedicated WSGI server with an `emptyDir` volume for temporary files.
- The crash endpoint is unauthenticated by design for the demo. Do not expose it on a production service.
- The Cloudflare quick tunnel has no uptime guarantee, and its URL changes each time it restarts.