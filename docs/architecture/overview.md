# Architecture Overview

CogniMesh is split into a control plane and a data plane.

The control plane owns metadata, object definitions, policies, lineage, workflow definitions, app registrations, and operational APIs. The data plane owns source connections, lakehouse storage, compute engines, query execution, and model serving.

Core boundaries:

- Storage is not the semantic layer.
- Compute engines are replaceable.
- Object APIs are the contract for apps and consumers.
- Policy checks happen before data access.
- Lineage is emitted by ingestion, transformations, actions, apps, and models.

The initial architecture is documented in [plan.md](../../plan.md). Architecture decisions are recorded in `docs/adr/`.

