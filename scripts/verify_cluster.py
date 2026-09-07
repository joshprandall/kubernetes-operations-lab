"""Exercise ONLY the dedicated kind-operations-lab context and operations-lab namespace."""
import json
from pathlib import Path
import subprocess
import time

CONTEXT = 'kind-operations-lab'
PREFIX = ['kubectl', '--context', CONTEXT, '--namespace', 'operations-lab']
EVENTS = []


def kubectl(*args, timeout=180):
    result = subprocess.run(PREFIX + list(args), capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def wait_for(description, condition, timeout=100):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            passed = condition()
        except (RuntimeError, subprocess.TimeoutExpired, StopIteration) as error:
            last_error = str(error)
            passed = False
        if passed:
            print('PASS ' + description, flush=True)
            EVENTS.append({'check': description, 'result': 'passed'})
            return
        time.sleep(2)
    raise TimeoutError(description + (f": {last_error}" if last_error else ""))


def pods():
    return [p for p in json.loads(kubectl('get', 'pods', '-l', 'app=operations-lab', '-o', 'json'))['items'] if not p['metadata'].get('deletionTimestamp')]


def ready(pod):
    return any(c['type'] == 'Ready' and c['status'] == 'True' for c in pod.get('status', {}).get('conditions', []))


def count_ready():
    return sum(ready(p) for p in pods())


def endpoint_count():
    data = json.loads(kubectl('get', 'endpointslices', '-l', 'kubernetes.io/service-name=operations-lab', '-o', 'json'))
    return sum(e.get('conditions', {}).get('ready') is True for item in data['items'] for e in item.get('endpoints', []))


def service_status():
    pod = next(p for p in pods() if ready(p))['metadata']['name']
    code = "import urllib.request; print(urllib.request.urlopen('http://operations-lab:8080/api/status', timeout=5).read().decode())"
    return json.loads(kubectl('exec', pod, '--', 'python', '-c', code))


def rollout():
    kubectl('rollout', 'status', 'deployment/operations-lab', '--timeout=150s')


def main():
    evidence = Path('.evidence')
    evidence.mkdir(exist_ok=True)
    try:
        rollout()
        wait_for('two ready replicas and service endpoints', lambda: count_ready() == 2 and endpoint_count() == 2)
        wait_for('service DNS and HTTP return v1', lambda: service_status()['version'] == 'v1')
        selected = pods()[0]
        name, uid = selected['metadata']['name'], selected['metadata']['uid']
        restarts = selected['status']['containerStatuses'][0]['restartCount']
        kubectl('exec', name, '--', 'python', '-c', "from pathlib import Path; Path('/tmp/not-ready').touch()")
        try:
            wait_for('unready replica removed from ready endpoints', lambda: endpoint_count() == 1 and count_ready() == 1)
            time.sleep(16)  # Cross the configured liveness failure window.
            same = json.loads(kubectl('get', 'pod', name, '-o', 'json'))
            if same['metadata']['uid'] != uid or same['status']['containerStatuses'][0]['restartCount'] != restarts:
                raise AssertionError('Readiness failure unexpectedly replaced or restarted the container.')
            wait_for('remaining service endpoint serves requests', lambda: service_status()['version'] == 'v1')
            EVENTS.append({'check': 'readiness failure does not trigger liveness restart', 'result': 'passed'})
        finally:
            kubectl('exec', name, '--', 'python', '-c', "from pathlib import Path; Path('/tmp/not-ready').unlink(missing_ok=True)")
        wait_for('readiness restored', lambda: count_ready() == 2 and endpoint_count() == 2)
        kubectl('delete', 'pod', name, '--wait=true')
        wait_for('deleted pod replaced with a new UID', lambda: len(pods()) == 2 and count_ready() == 2 and all(p['metadata']['uid'] != uid for p in pods()))
        kubectl('scale', 'deployment/operations-lab', '--replicas=3')
        wait_for('scale to three ready replicas', lambda: count_ready() == 3 and endpoint_count() == 3)
        kubectl('scale', 'deployment/operations-lab', '--replicas=2')
        wait_for('scale back to two', lambda: len(pods()) == 2 and count_ready() == 2)
        kubectl('set', 'env', 'deployment/operations-lab', 'APP_VERSION=v2')
        rollout()
        wait_for('v2 rollout serves new configuration', lambda: service_status()['version'] == 'v2')
        kubectl('set', 'image', 'deployment/operations-lab', 'api=operations-lab:missing')
        wait_for('bad image is waiting while two replicas remain ready', lambda: count_ready() == 2 and any(c.get('state', {}).get('waiting', {}).get('reason') == 'ErrImageNeverPull' for p in pods() for c in p.get('status', {}).get('containerStatuses', [])))
        kubectl('rollout', 'undo', 'deployment/operations-lab')
        rollout()
        wait_for('rollback restores working v2 revision', lambda: len(pods()) == 2 and count_ready() == 2 and service_status()['version'] == 'v2')
        kubectl('set', 'env', 'deployment/operations-lab', 'APP_VERSION=v1')
        rollout()
        wait_for('baseline configuration restored', lambda: service_status()['version'] == 'v1')
    except Exception as error:
        EVENTS.append({'check': 'cluster verification', 'result': 'failed', 'detail': str(error)})
        raise
    finally:
        (evidence / 'cluster-checks.json').write_text(json.dumps(EVENTS, indent=2) + '\n')
        print(json.dumps(EVENTS, indent=2), flush=True)


if __name__ == '__main__':
    main()
