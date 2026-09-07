# Upload and run

1. Create a public repository named `kubernetes-operations-lab`; leave starter README, license, and gitignore creation off.
2. Extract the ZIP and open the project folder containing Dockerfile and README.md.
3. Upload the contents, preserving app, k8s, scripts, and tests as folders. Commit with `Add Kubernetes operations lab`.
4. Confirm `.github/workflows/test.yml` exists. If it does not, choose Add file → Create new file, enter that exact path, and paste the complete workflow below.
5. Open Actions → Kubernetes lab checks. The service job should run before the cluster job. The first run may take several minutes to download images.
6. Only describe the cluster checks as passed once the cluster job is green. Open its failed step and diagnostics if it is red.

Description:

`Local Kubernetes lab with a Python service, readiness checks, scaling, pod replacement, rollout recovery, and automated cluster exercises.`

## Complete workflow

```yaml
name: Kubernetes lab checks
on:
  push:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  service:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@v7
        with:
          python-version: '3.13'
      - run: python -m pip install -r requirements-dev.txt
      - run: python -m unittest discover -s tests -v
      - run: python scripts/check_manifests.py
  cluster:
    needs: service
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@v7
        with:
          python-version: '3.13'
      - name: Install versioned lab tools
        shell: bash
        run: |
          set -euo pipefail
          mkdir -p "$RUNNER_TEMP/lab-bin"
          curl --fail --location --retry 3 https://kind.sigs.k8s.io/dl/v0.33.0/kind-linux-amd64 -o "$RUNNER_TEMP/lab-bin/kind"
          curl --fail --location --retry 3 https://dl.k8s.io/release/v1.35.8/bin/linux/amd64/kubectl -o "$RUNNER_TEMP/lab-bin/kubectl"
          curl --fail --location --retry 3 https://dl.k8s.io/release/v1.35.8/bin/linux/amd64/kubectl.sha256 -o "$RUNNER_TEMP/lab-bin/kubectl.sha256"
          cd "$RUNNER_TEMP/lab-bin"
          echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check
          chmod +x kind kubectl
          echo "$RUNNER_TEMP/lab-bin" >> "$GITHUB_PATH"
      - name: Build image and deploy to kind
        run: python scripts/lab.py up
      - name: Exercise readiness, replacement, scaling, and rollback
        run: python scripts/lab.py verify
      - name: Diagnostic state
        if: always()
        shell: bash
        run: |
          kubectl --context kind-operations-lab -n operations-lab get pods -o wide || true
          kubectl --context kind-operations-lab -n operations-lab get events --sort-by=.metadata.creationTimestamp || true
          kubectl --context kind-operations-lab -n operations-lab describe deployment operations-lab || true
          if [ -f .evidence/cluster-checks.json ]; then cat .evidence/cluster-checks.json; fi
      - name: Remove temporary CI cluster
        if: always()
        run: kind delete cluster --name operations-lab
```

Official action references: https://github.com/actions/checkout and https://github.com/actions/setup-python
