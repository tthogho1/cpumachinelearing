# Kubernetes manifests

Two workloads sharing one PVC (`model-output-pvc`) for the saved model bundle:

1. **`job-train-model.yaml`** — a `Job` that runs `train_model.py --save-model
   output/models_h12.joblib` once, writing the trained model bundle to the PVC.
2. **`deployment-webapp.yaml`** — a `Deployment` + `Service` that runs `webapp/app.py`,
   reading `output/models_h12.joblib` from the same PVC to serve forecasts (Flask API
   + built React frontend from the image).

Both manifests reference `ghcr.io/tthogho1/cpumachinelearning-webapp:latest`, built
from the repo's `Dockerfile` (see root `README.md` / `docker compose build`) and
published automatically by [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml)
on every push to `main` (tag `latest`) and on `v*.*.*` tags (semver + short-SHA tags).
Any real multi-node cluster (EKS/GKE/AKS/etc.) can pull this image directly — no
local build step is required there.

## Pulling the image on a real cluster

On a real (multi-node) cluster, nodes don't share a Docker daemon with your
workstation, so they pull `ghcr.io/tthogho1/cpumachinelearning-webapp:latest`
directly from the registry — no local `docker build` is needed before `kubectl
apply`.

**GHCR visibility:** packages pushed via `GITHUB_TOKEN` are created **private** by
default, so the cluster can't pull them until you make the package public:

1. Push to `main` (or run the workflow manually) so `.github/workflows/docker-publish.yml`
   publishes the image at least once — the package doesn't exist on GHCR before that.
2. On GitHub, go to the repo → right sidebar **Packages** → `cpumachinelearning-webapp`
   (or `https://github.com/users/tthogho1/packages/container/package/cpumachinelearning-webapp`).
3. **Package settings** (bottom of the page) → **Danger Zone** → **Change visibility**
   → select **Public** → confirm by typing the package name.

Once public, `kubectl apply` on any cluster can pull the image with no credentials
or `imagePullSecrets` needed — the manifests already work as-is.

<details>
<summary>Alternative: keep the package private and use an imagePullSecret</summary>

If you'd rather not make the package public, create a pull secret from a
[GitHub Personal Access Token](https://github.com/settings/tokens) (classic,
scope `read:packages`) and reference it from the pods:

```sh
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=<your-github-username> \
  --docker-password=<your PAT with read:packages scope> \
  -n inflation-forecast
```

then add to both `job-train-model.yaml` and `deployment-webapp.yaml`'s pod
`spec:`:

```yaml
spec:
  imagePullSecrets:
    - name: ghcr-pull-secret
```

</details>

To pin a specific CI-built tag (e.g. a git-SHA tag) instead of `latest`, edit the
`images:` entry in [`kustomization.yaml`](kustomization.yaml) and apply with
`kubectl apply -k k8s/`.

## Apply

Order matters: the training Job should complete before the webapp Deployment starts,
since the webapp expects `output/models_h12.joblib` to already exist on the PVC.

```sh
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pvc-output.yaml

# Job 1: train and save the model
kubectl apply -f k8s/job-train-model.yaml
kubectl wait --for=condition=complete job/train-model -n inflation-forecast --timeout=300s

# Job 2: start serving forecasts from the saved model
kubectl apply -f k8s/deployment-webapp.yaml
```

Or, with kustomize (applies everything, but doesn't wait between steps — run the
`kubectl wait` above manually if you use this):

```sh
kubectl apply -k k8s/
```

## Check status

```sh
kubectl get jobs,pods,pvc -n inflation-forecast
kubectl logs -n inflation-forecast job/train-model
kubectl logs -n inflation-forecast deploy/webapp
```

## Access the webapp

```sh
kubectl port-forward -n inflation-forecast svc/webapp 8080:80
# open http://127.0.0.1:8080/
```

## Retrain later

Re-running the Job requires deleting the old one first (Jobs are immutable):

```sh
kubectl delete job train-model -n inflation-forecast
kubectl apply -f k8s/job-train-model.yaml
kubectl wait --for=condition=complete job/train-model -n inflation-forecast --timeout=300s
kubectl rollout restart deployment/webapp -n inflation-forecast   # pick up the new model file
```

## Clean up

```sh
kubectl delete namespace inflation-forecast
```
