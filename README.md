# SLSA Level 3 Compliant Hardened Kubernetes Pipeline

An enterprise-grade, zero-trust DevSecOps pipeline achieving **SLSA Level 3 (Supply-chain Levels for Software Artifacts)** compliance. This project demonstrates advanced cloud-native security principles, featuring a shell-less multi-stage container runtime orchestrated via a highly secure, rootless Kubernetes cluster blueprint.

---

## 🏗️ Architecture & Security Topology



The system enforces a strict defense-in-depth model across the entire software development lifecycle:

1. **Supply Chain Security (SLSA Level 3):** Fully automated CI/CD workflows generating non-falsifiable provenance documentation, guaranteeing artifact integrity from code commit to cluster deployment.
2. **Attack Surface Minimization (Distroless/Shell-less):** Multi-stage Docker compilation that completely strips out standard execution shells (\/bin/sh\, \/bin/bash\) and high-risk binaries (\curl\, \wget\).
3. **Kernel-Level Workload Isolation:** Enforces explicit K8s \securityContext\ boundaries blocking privilege escalation, dropping all core Linux capabilities, and restricting execution to a non-root user account.
4. **Immutable Runtime Environment:** The root filesystem is mounted as read-only (\eadOnlyRootFilesystem: true\), preventing post-exploitation payloads or unauthorized runtime mutations.

---

## 🛡️ Hardening Specifications

### Container Security Profile
| Security Feature | Implementation Mechanism | Purpose |
| :--- | :--- | :--- |
| **User Space** | Unprivileged UID/GID \10001\ | Eliminates root-level host container breakouts |
| **Filesystem** | Read-Only Root OS | Prevents file injection and runtime script mutations |
| **Privileges** | \llowPrivilegeEscalation: false\ | Disallows child processes from gaining more rights than parents |
| **Capabilities** | \capabilities.drop: ["ALL"]\ | Strips all Linux kernel system call privileges |

### Kubernetes Resiliency Mesh
* **Dual Replicas:** Automated high-availability layout managed by a K8s Deployment controller.
* **Probes:** Custom HTTP liveness and readiness monitors checking application health dynamically.
* **Service Abstracting:** Load-balanced cluster routing via a NodePort Service structure.

---

## 🚀 Local Deployment & Verification

### Prerequisites
* Docker Desktop (with Kubernetes / \kind\ cluster active)
* \kubectl\ CLI client

### 1. Execute the Deployment Manifest
\\\powershell
kubectl apply -f deployment.yaml
\\\

### 2. Verify Workload Sandboxing
Inspect the enforcement logs to mathematically verify container isolation constraints:
\\\powershell
kubectl get deployment slsa-hardened-app -o jsonpath='{.spec.template.spec.containers[0].securityContext}'
\\\

### 3. Establish Local Access Proxy Tunnel
Since the network cluster layer runs inside an isolated virtual node mesh, open an authenticated gateway tunnel:
\\\powershell
kubectl port-forward service/slsa-app-service 8080:80
\\\
Access the verified live endpoints via your browser: \http://localhost:8080/health\
"@