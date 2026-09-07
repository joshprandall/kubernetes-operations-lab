# Validation record

- Python 3.12.13, Linux: 12 HTTP service tests passed.
- 12 static manifest consistency checks passed using PyYAML.
- Python source compiled successfully.
- Docker/kubectl/kind were unavailable in the build environment. The local lab launcher correctly reported missing Docker.
- Container build, Kubernetes API admission, and real cluster exercises remain unverified until the included GitHub Actions cluster job or a local lab run succeeds.
- No cluster results have been fabricated or bundled. `scripts/verify_cluster.py` generates `.evidence/cluster-checks.json` from actual observations when executed.
