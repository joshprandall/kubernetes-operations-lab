"""Build and deploy a dedicated local kind lab; never uses your default context."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NODE_IMAGE = 'kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0'


def run(*args):
    print('> ' + ' '.join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['up', 'verify'])
    action = parser.parse_args().action
    for command in ('docker', 'kind', 'kubectl'):
        if not shutil.which(command):
            raise SystemExit(f'Missing {command}. See README prerequisites.')
    if action == 'verify':
        run(sys.executable, 'scripts/verify_cluster.py')
        return
    clusters = subprocess.check_output(['kind', 'get', 'clusters'], text=True).splitlines()
    if 'operations-lab' in clusters:
        raise SystemExit('The operations-lab cluster already exists. Use verify or inspect it before creating a fresh lab.')
    run('docker', 'info')
    run('docker', 'build', '-t', 'operations-lab:1.0.0', '.')
    run('kind', 'create', 'cluster', '--name', 'operations-lab', '--config', 'kind.yaml', '--image', NODE_IMAGE, '--wait', '180s')
    run('kind', 'load', 'docker-image', 'operations-lab:1.0.0', '--name', 'operations-lab')
    prefix = ('kubectl', '--context', 'kind-operations-lab')
    run(*prefix, 'apply', '-f', 'k8s/namespace.yaml')
    run(*prefix, 'apply', '--dry-run=server', '-f', 'k8s/workload.yaml')
    run(*prefix, 'apply', '-f', 'k8s/workload.yaml')
    run(*prefix, '-n', 'operations-lab', 'rollout', 'status', 'deployment/operations-lab', '--timeout=150s')
    print('Lab created. Run: python scripts/lab.py verify')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f'Command failed with exit {error.returncode}. Existing lab resources were preserved for inspection.')
