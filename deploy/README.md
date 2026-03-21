# OpenClaw Multi-Agent Framework

Base configuration for OpenClaw deployment.

## Components

- Control Plane API Server
- Worker Runtime
- PostgreSQL (optional external)
- Redis (optional external)
- Monitoring (Prometheus/Grafana)

## Usage

```bash
# Development
kubectl kustomize deploy/overlays/dev | kubectl apply -f -

# Production
kubectl kustomize deploy/overlays/prod | kubectl apply -f -
```

## Architecture

```
                    ┌─────────────┐
                    │   Gateway   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │Control Plane│
                    │   (API)     │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
    │ Worker │       │ Worker │       │ Worker  │
    │  (1)   │       │  (2)   │       │  (n)    │
    └─────────┘       └─────────┘       └─────────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Redis     │
                    │  + Postgres │
                    └─────────────┘
```