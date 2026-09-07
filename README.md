# Kubernetes Operations Lab

Operate a small Python HTTP service on a dedicated local Kubernetes cluster. Demonstrate readiness-based traffic eligibility, pod replacement, replica scaling, rolling configuration changes, and recovery from a bad image rollout.

**Validation status:** 12 HTTP service tests and 12 static manifest checks passed locally. Docker and Kubernetes were unavailable in the build workspace, so the container build and cluster exercises have **not yet been executed there**. The included GitHub Actions workflow runs those checks in a temporary kind cluster after upload. Treat cluster behavior as pending verification until that job succeeds.

## What is included

| Component | Purpose |
| --- | --- |
| Python service | JSON status endpoint, separate readiness/liveness, request counter, JSON logs |
| Dockerfile | Dependency-free service running as UID/GID 10001 |
| Deployment | Two replicas, startup/readiness/liveness probes, rolling updates, resource requests/limits |
| ClusterIP Service | Stable in-cluster service address selecting the application pods |
| ConfigMap | Nonsecret message configuration |
| PodDisruptionBudget | Minimum one available replica for supported voluntary eviction operations |
| Container controls | Read-only root filesystem, dropped capabilities, no privilege escalation, no mounted service-account token |
| Cluster exercises | Real kubectl operations with recorded pass/fail evidence |
| CI workflow | Local tests, image build, server-side manifest dry-run, temporary cluster exercises |

The three kind nodes run as containers on one host. This is a local learning environment, not infrastructure that survives losing the host. There is no public ingress, authentication, persistent database, autoscaler, or NetworkPolicy enforcement in this project. The Python standard-library HTTP server is for the lab, not an internet-facing production application.

## Start with GitHub if Docker is not installed

Upload this project and its `.github/workflows/test.yml`, then open **Actions → Kubernetes lab checks**. The `service` job runs first; `cluster` then builds and tests the lab. Inspect the first failed step if either job fails. The cluster job uses a temporary GitHub runner and does not require a cloud account or cloud credentials.

See [GITHUB_SETUP.md](GITHUB_SETUP.md) for the full workflow to copy if browser upload omits the workflow directory.

## Local prerequisites

- Python 3.10+ for the scripts; the container uses Python 3.13.
- A running Docker engine using Linux containers. On Windows, follow [Docker Desktop installation](https://docs.docker.com/desktop/setup/install/windows-install/).
- [kind v0.33.0](https://kind.sigs.k8s.io/docs/user/quick-start/) and [kubectl](https://kubernetes.io/docs/tasks/tools/). The workflow uses kubectl v1.35.8 to match its Kubernetes node image.
- Network access for initial tool/image downloads; enough local resources for three kind nodes. No cloud deployment is needed.

The kind node image is pinned by digest to the v1.35.8 image listed in the [kind release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0). The Python base image uses the mutable `python:3.13-slim` tag; rebuilds may include updated base layers. This project does not claim byte-for-byte container reproducibility.

## Create the lab

From the extracted project folder:

```sh
python scripts/lab.py up
python scripts/lab.py verify
```

On Windows, `py` can replace `python` if that is how Python is installed. The scripts use explicit `kind-operations-lab` context and `operations-lab` namespace. `up` refuses to replace an existing cluster with that name. If creation fails partway through, resources are retained for inspection.

`verify` deliberately changes readiness, deletes one application pod, scales replicas, changes the displayed version, and deploys an unavailable image before rolling back. Use the dedicated lab cluster only. A successful run restores two replicas and displayed version v1. On failure, inspect the state before resetting or deleting the lab.

To view the service, keep this command running in another terminal:

```sh
kubectl --context kind-operations-lab -n operations-lab port-forward service/operations-lab 8080:8080
```

Open http://localhost:8080/api/status in your browser. This is a JSON API, not a graphical dashboard. Port-forward selects a backing pod; it is not a demonstration of per-request load balancing. A pod replacement can require restarting port-forward.

## Endpoint contract

| GET path | Behavior |
| --- | --- |
| `/` or `/api/status` | Service name, displayed version, message, pod hostname, uptime |
| `/healthz` | HTTP 200 while the server can respond |
| `/readyz` | HTTP 503 while `/tmp/not-ready` exists or the server is draining; otherwise 200 |
| `/metrics` | Prometheus text-format GET request counter; includes probes and metrics scrapes |
| Unknown path | JSON 404 |

No HTTP endpoint creates failure markers. The readiness exercise uses authorized `kubectl exec`. Metrics are per process and reset on restart; no Prometheus installation or durable metrics store is included. SIGTERM marks the process draining and requests server shutdown; the lab does not guarantee completion of arbitrary long-running requests.

## Validation commands

```sh
python -m unittest discover -s tests -v
python -m pip install -r requirements-dev.txt
python scripts/check_manifests.py
```

PyYAML is a development dependency only. Static checks detect internal manifest inconsistencies; they are not Kubernetes API validation. `lab.py up` also performs a server-side dry-run after creating the namespace. `verify_cluster.py` prints each successful condition and writes `.evidence/cluster-checks.json`; failures return a nonzero process exit.

See [RUNBOOK.md](RUNBOOK.md) for exercises and [DESIGN.md](DESIGN.md) for assumptions and tradeoffs.

## Clean up

After you finish, this removes the dedicated lab cluster and its contents:

```sh
kind delete cluster --name operations-lab
```

The locally built `operations-lab:1.0.0` Docker image remains available. No cleanup command in this project removes unrelated Docker resources.
