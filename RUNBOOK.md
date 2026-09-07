# Operations exercises

Run from the project root after `python scripts/lab.py up`. Commands below use the dedicated context explicitly. For the complete automated sequence, use `python scripts/lab.py verify`; it records checks in `.evidence/cluster-checks.json`.

## 1. Establish baseline

```sh
kubectl --context kind-operations-lab -n operations-lab get deployment,pods,service,pdb -o wide
kubectl --context kind-operations-lab -n operations-lab get endpointslices
```

Expected: desired replicas 2, eventually two Ready pods and two ready service endpoints. Investigate Pending, image, or readiness failures before moving on. Pod placement is a scheduling preference, not a promise.

## 2. Scale deliberately

```sh
kubectl --context kind-operations-lab -n operations-lab scale deployment/operations-lab --replicas=3
kubectl --context kind-operations-lab -n operations-lab rollout status deployment/operations-lab --timeout=150s
kubectl --context kind-operations-lab -n operations-lab get pods -o wide
kubectl --context kind-operations-lab -n operations-lab scale deployment/operations-lab --replicas=2
```

Explain the desired replica count and how the controller works toward it. This is manual scaling, not CPU-based autoscaling.

## 3. Make one replica unready

In PowerShell, select one pod and create its marker:

```powershell
$labPod = kubectl --context kind-operations-lab -n operations-lab get pods -l app=operations-lab -o jsonpath='{.items[0].metadata.name}'
kubectl --context kind-operations-lab -n operations-lab exec $labPod -- python -c "from pathlib import Path; Path('/tmp/not-ready').touch()"
kubectl --context kind-operations-lab -n operations-lab get pods
kubectl --context kind-operations-lab -n operations-lab get endpointslices -o yaml
```

Within probe and controller update delays, expect one pod to become not Ready. Its EndpointSlice endpoint should be marked not ready; it may remain listed. The health endpoint still responds, so this condition should not trigger liveness restarts. The automated exercise checks the same pod UID and unchanged restart count after the liveness failure window.

Restore it:

```powershell
kubectl --context kind-operations-lab -n operations-lab exec $labPod -- python -c "from pathlib import Path; Path('/tmp/not-ready').unlink(missing_ok=True)"
kubectl --context kind-operations-lab -n operations-lab wait --for=condition=Ready pod/$labPod --timeout=60s
```

For Bash users, run the cross-platform `python scripts/lab.py verify` to perform this exercise without translating the PowerShell variable syntax.

## 4. Replace a deleted pod

After both pods are Ready, in the same PowerShell session:

```powershell
kubectl --context kind-operations-lab -n operations-lab delete pod $labPod
kubectl --context kind-operations-lab -n operations-lab get pods -w
```

Press Ctrl+C once the replacement is Ready. A new pod has a different UID. This is controller replacement, not the same as a container restarting inside a pod. Direct deletion is not prevented by a PodDisruptionBudget.

## 5. Roll out a version label

```sh
kubectl --context kind-operations-lab -n operations-lab set env deployment/operations-lab APP_VERSION=v2
kubectl --context kind-operations-lab -n operations-lab rollout status deployment/operations-lab --timeout=150s
kubectl --context kind-operations-lab -n operations-lab rollout history deployment/operations-lab
```

APP_VERSION is a displayed configuration value, not new application code. Changing it changes the pod template and triggers a rollout. The strategy permits one extra pod and zero unavailable replicas during the rollout; it requires enough capacity for the extra pod.

## 6. Break the next rollout and recover

```sh
kubectl --context kind-operations-lab -n operations-lab set image deployment/operations-lab api=operations-lab:missing
kubectl --context kind-operations-lab -n operations-lab get pods
kubectl --context kind-operations-lab -n operations-lab describe deployment operations-lab
```

The intentionally absent image cannot run because imagePullPolicy is Never. Expect ErrImageNeverPull on the new pod while the previous two healthy replicas remain available, assuming the cluster stays healthy. Kubernetes does not automatically roll back this deployment.

```sh
kubectl --context kind-operations-lab -n operations-lab rollout undo deployment/operations-lab
kubectl --context kind-operations-lab -n operations-lab rollout status deployment/operations-lab --timeout=150s
kubectl --context kind-operations-lab -n operations-lab set env deployment/operations-lab APP_VERSION=v1
kubectl --context kind-operations-lab -n operations-lab rollout status deployment/operations-lab --timeout=150s
```

Undo restores the previous pod template, which should be the working v2 configuration if you followed this sequence. It does not roll back database contents or ConfigMap edits.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| Missing docker / engine connection error | Docker installation and whether the Linux engine is running |
| ErrImageNeverPull on initial deployment | `kind load docker-image operations-lab:1.0.0 --name operations-lab` completed |
| Pods Pending | `describe pod`; inspect capacity, scheduling, and admission events |
| Pod Running but not Ready | `/tmp/not-ready`, readiness-probe events, and application logs |
| Port-forward stops | Selected pod was replaced; restart port-forward |
| Rollout times out | Image availability, probe failures, capacity, and deployment events |
| GitHub shows workflow templates | Confirm the file exists at `.github/workflows/test.yml` |

Inspect logs:

```sh
kubectl --context kind-operations-lab -n operations-lab logs deployment/operations-lab --tail=30
kubectl --context kind-operations-lab -n operations-lab get events --sort-by=.metadata.creationTimestamp
```

To reset declared workload state after inspection, reapply `k8s/workload.yaml` using the explicit context. This resets desired replicas and pod-template settings; it does not remove a marker from a surviving pod. The most complete reset is deleting and recreating this dedicated lab cluster.
