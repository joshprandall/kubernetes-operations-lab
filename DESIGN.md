# Design and limits

The Python service demonstrates an operational contract that the Kubernetes configuration consumes. The app does not query the Kubernetes API. Pod identity comes from hostname, configuration comes from environment variables, and logs go to stdout.

## Probes

Startup allows the service to begin responding before normal probes take over. Readiness controls endpoint eligibility; liveness checks whether this HTTP process can answer. External service dependencies are deliberately absent, so a failed dependency does not trigger a misleading restart loop. These probes demonstrate mechanics, not comprehensive application health. See [Kubernetes probe documentation](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/).

## Rollouts and disruption

The Deployment starts with two replicas and uses maxSurge 1 / maxUnavailable 0. That trades spare capacity for retaining available replicas during an update. The PDB asks eviction-aware operations to retain one available pod. It does not prevent node failure or direct deletion, and it does not govern Deployment rolling updates. See [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) and [disruption budgets](https://kubernetes.io/docs/tasks/run-application/configure-pdb/).

Preferred anti-affinity encourages different nodes but is not mandatory. The local nodes all share one Docker host, so placement does not establish host-level high availability. There is no measured zero-downtime claim.

## Configuration and containment

The ConfigMap is for a nonsecret display message. Environment-based ConfigMap values are captured when a container starts; editing the map alone does not update the running process. APP_VERSION is directly set in the pod template for a clear rollout exercise. See [ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/).

The container runs without root, extra Linux capabilities, privilege escalation, or a service-account token. Its root filesystem is read-only, with a bounded /tmp volume for the exercise marker. The namespace enforces restricted Pod Security admission using the cluster's latest policy version, which may add requirements on future Kubernetes upgrades. This does not provide network isolation, user authentication, image scanning, or supply-chain verification. See [security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/).

## Resource and metrics choices

CPU/memory requests and limits are small teaching defaults, not values derived from load testing. The request counter is per process, counts all GET requests including probes, and resets with the process. Metrics-server, Prometheus, dashboards, and HPA are not installed. The next extension could add measured load, resource tuning, and autoscaling after a metrics pipeline is verified. See [resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).

## Reproducibility

The kind node image is digest-pinned. kind and kubectl versions are explicit in CI; kubectl's download is checked against its published SHA-256. The kind tool download uses a versioned official HTTPS URL. Python's container base uses a mutable minor-version tag. GitHub actions use major-version tags. This balances readable lab configuration and maintenance, but is not fully immutable supply-chain pinning.

## Evidence

Local verification covers real HTTP responses and static YAML relationships. Cluster verification checks ready replicas and endpoints, in-cluster DNS/HTTP, unchanged restart count during readiness failure, pod replacement UID, scaling, configuration rollout, a waiting bad image, rollback, and restoration. It records observed passes, not prefilled results. The workload is stateless; rollback does not claim to restore data.
