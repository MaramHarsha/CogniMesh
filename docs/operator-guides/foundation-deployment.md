# Foundation Deployment Guide

Module 0 deployment assets are scaffolds. They prove the repository has a consistent local and Kubernetes layout before runtime services exist.

## Compose

The Compose file defines a `foundation` profile with a lightweight placeholder service.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\of.ps1 compose:up
```

Module 1 will add PostgreSQL and the Object Registry service.

## Helm

The Helm chart at `infra/helm/cognimesh` is an umbrella placeholder. Runtime templates are added as modules are implemented.

## Kustomize

The base at `infra/kustomize/base` is intentionally empty until Kubernetes resources exist.
