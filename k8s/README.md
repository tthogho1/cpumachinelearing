# Kubernetes manifests

Two workloads sharing one PVC (`model-output-pvc`) for the saved model bundle:

1. **`job-train-model.yaml`** — a `Job` that runs `train_model.py --save-model
   output/models_h12.joblib` once, writing the trained model bundle to the PVC.
2. **`deployment-webapp.yaml`** — a `Deployment` + `Service` that runs `webapp/app.py`,
   reading `output/models_h12.joblib` from the same PVC to serve forecasts (Flask API
   + built React frontend from the image).

Both use the image `cpumachinelearning-webapp:latest` built from the repo's
`Dockerfile` (see root `README.md` / `docker compose build`).

## Build the image for your cluster

For local clusters that use the host's Docker daemon (Docker Desktop's built-in
Kubernetes), a local `docker build` is enough:

```sh
docker build -t cpumachinelearning-webapp:latest .
```

For `kind`, load the image into the cluster:

```sh
docker build -t cpumachinelearning-webapp:latest .
kind load docker-image cpumachinelearning-webapp:latest
```

For `minikube`:

```sh
eval $(minikube docker-env)
docker build -t cpumachinelearning-webapp:latest .
```

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
