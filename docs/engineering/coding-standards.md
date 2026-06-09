# Coding Standards

These standards apply unless a module-specific ADR changes them.

## Python

- Use Python 3.12 or newer.
- Use type hints for public functions and service boundaries.
- Keep FastAPI route handlers thin; move business logic into services.
- Use Pydantic models for API payload validation.
- Use SQLAlchemy and Alembic for relational persistence.
- Use structured logging.
- Add tests for service logic, API contracts, and integration paths.

## TypeScript

- Use TypeScript in strict mode.
- Keep API clients generated or typed from OpenAPI/GraphQL schemas.
- Keep UI state separate from API transport logic.
- Prefer small object-aware components over raw table-specific components.
- Add component and API contract tests once frontend modules begin.

## Docker

- Use multi-stage builds when runtime images need build dependencies.
- Pin major base image versions.
- Run services as non-root users.
- Expose health endpoints and document ports.
- Keep secrets out of images and Compose files.

## SQL

- Prefer explicit column lists.
- Use stable semantic names in models and object mappings.
- Use migrations for metadata schemas.
- Avoid raw string query construction in services.
- Add data quality checks for primary keys, required fields, and relationships.

## YAML

- Keep configuration minimal and environment-specific values externalized.
- Use two-space indentation.
- Avoid anchors unless they materially reduce duplication.
- Validate Compose, Helm, and workflow files in CI when tooling is available.

