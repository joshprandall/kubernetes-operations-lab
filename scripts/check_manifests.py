"""Static consistency checks; requires PyYAML. Not a Kubernetes API validation."""
from pathlib import Path
import yaml

root = Path(__file__).resolve().parents[1]
resources = list(yaml.safe_load_all((root / 'k8s/workload.yaml').read_text()))
objects = {r['kind']: r for r in resources}
deployment = objects['Deployment']
pod = deployment['spec']['template']
container = pod['spec']['containers'][0]
checks = {
    'all workload resources scoped to lab': all(r['metadata']['namespace'] == 'operations-lab' for r in resources),
    'deployment selector matches pod labels': deployment['spec']['selector']['matchLabels'] == pod['metadata']['labels'],
    'service selector matches pods': objects['Service']['spec']['selector'] == pod['metadata']['labels'],
    'budget selector matches pods': objects['PodDisruptionBudget']['spec']['selector']['matchLabels'] == pod['metadata']['labels'],
    'two replicas with no unavailable rollout pods': deployment['spec']['replicas'] == 2 and deployment['spec']['strategy']['rollingUpdate']['maxUnavailable'] == 0,
    'separate readiness and liveness probes': container['readinessProbe']['httpGet']['path'] == '/readyz' and container['livenessProbe']['httpGet']['path'] == '/healthz',
    'nonroot read-only container without escalation': pod['spec']['securityContext']['runAsNonRoot'] and container['securityContext']['readOnlyRootFilesystem'] and not container['securityContext']['allowPrivilegeEscalation'],
    'no service account token mount': pod['spec']['automountServiceAccountToken'] is False,
    'all capabilities dropped': container['securityContext']['capabilities']['drop'] == ['ALL'],
    'local image and named port consistent': container['imagePullPolicy'] == 'Never' and objects['Service']['spec']['ports'][0]['targetPort'] == container['ports'][0]['name'],
    'resource requests and limits specified': all(k in container['resources'][t] for t in ('requests','limits') for k in ('cpu','memory')),
    'configmap reference resolves': container['envFrom'][0]['configMapRef']['name'] == objects['ConfigMap']['metadata']['name'],
}
for name, passed in checks.items():
    print(('PASS ' if passed else 'FAIL ') + name)
if not all(checks.values()):
    raise SystemExit(1)
print(f'{len(checks)} static checks passed')
