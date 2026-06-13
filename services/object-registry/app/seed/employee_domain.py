from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.security import RequestContext
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.dataset import DatasetTable
from app.models.link_type import LinkType
from app.models.namespace import Namespace
from app.models.object_property import ObjectProperty
from app.models.object_type import ObjectType
from app.models.source_system import SourceSystem
from app.models.workspace import Workspace
from app.schemas.dataset_table import DatasetColumnCreate, DatasetTableCreate
from app.schemas.link_type import LinkTypeCreate
from app.schemas.namespace import NamespaceCreate
from app.schemas.object_property import ObjectPropertyCreate
from app.schemas.object_type import ObjectTypeCreate
from app.schemas.source_system import SourceSystemCreate
from app.schemas.workspace import WorkspaceCreate
from app.services.policy_service import policy_service
from app.services.registry_service import registry_service


def seed_context() -> RequestContext:
    return RequestContext(
        actor="seed:employee-domain",
        subject="seed:employee-domain",
        principal_id=None,
        principal_type="service_account",
        workspace_id=None,
        roles=("platform_admin",),
        groups=("seed",),
        purpose="metadata_administration",
        attributes={"seed": "employee_domain"},
    )


def scalar_one_or_none(session: Session, statement):
    return session.scalar(statement)


def ensure_workspace(session: Session, context: RequestContext) -> Workspace:
    existing = scalar_one_or_none(session, select(Workspace).where(Workspace.slug == "default"))
    if existing:
        return existing
    decision = policy_service.authorize(session, context, "create", "workspace")
    return registry_service.create_workspace(
        session,
        WorkspaceCreate(name="Default Workspace", slug="default", description="Default CogniMesh workspace"),
        context,
        decision,
    )


def ensure_namespace(session: Session, workspace: Workspace, context: RequestContext) -> Namespace:
    existing = scalar_one_or_none(
        session,
        select(Namespace).where(Namespace.workspace_id == workspace.id, Namespace.api_name == "hr"),
    )
    if existing:
        return existing
    decision = policy_service.authorize(session, context, "create", "namespace", workspace.id)
    return registry_service.create_namespace(
        session,
        NamespaceCreate(
            workspace_id=workspace.id,
            name="Human Resources",
            api_name="hr",
            description="Employee, department, and project workforce domain",
        ),
        context,
        decision,
    )


def ensure_source(session: Session, namespace: Namespace, context: RequestContext) -> SourceSystem:
    existing = scalar_one_or_none(
        session,
        select(SourceSystem).where(SourceSystem.namespace_id == namespace.id, SourceSystem.api_name == "hr_postgres"),
    )
    if existing:
        return existing
    decision = policy_service.authorize(session, context, "create", "source_system", namespace.id)
    return registry_service.create_source_system(
        session,
        SourceSystemCreate(
            namespace_id=namespace.id,
            api_name="hr_postgres",
            name="HR PostgreSQL",
            source_type="postgresql",
            description="Synthetic HR source database",
            connection_uri="postgresql://hr.example.internal/hr",
            classification_tags=["internal"],
            allowed_purposes=["metadata_administration", "payroll", "workforce_planning"],
            owner_group="hr-data-owners",
            steward_group="hr-data-stewards",
        ),
        context,
        decision,
    )


def ensure_table(
    session: Session,
    namespace: Namespace,
    source: SourceSystem,
    context: RequestContext,
    payload: DatasetTableCreate,
) -> DatasetTable:
    existing = scalar_one_or_none(
        session,
        select(DatasetTable).where(
            DatasetTable.namespace_id == namespace.id,
            DatasetTable.physical_name == payload.physical_name,
        ),
    )
    if existing:
        return existing
    decision = policy_service.authorize(session, context, "create", "dataset_table", namespace.id)
    return registry_service.create_dataset_table(session, payload, context, decision)


def ensure_object_type(
    session: Session,
    namespace: Namespace,
    context: RequestContext,
    payload: ObjectTypeCreate,
    properties: list[ObjectPropertyCreate],
) -> ObjectType:
    existing = scalar_one_or_none(
        session,
        select(ObjectType).where(ObjectType.namespace_id == namespace.id, ObjectType.api_name == payload.api_name),
    )
    if existing:
        object_type = existing
    else:
        decision = policy_service.authorize(session, context, "create", "object_type", namespace.id)
        object_type = registry_service.create_object_type(session, payload, context, decision)

    existing_props = {
        prop.api_name
        for prop in session.scalars(
            select(ObjectProperty).where(ObjectProperty.object_type_id == object_type.id)
        ).all()
    }
    for prop in properties:
        if prop.api_name in existing_props:
            continue
        decision = policy_service.authorize(session, context, "create", "object_property", object_type.id)
        registry_service.create_object_property(session, object_type.id, prop, context, decision)
    return object_type


def ensure_link(session: Session, namespace: Namespace, context: RequestContext, payload: LinkTypeCreate) -> LinkType:
    existing = scalar_one_or_none(
        session,
        select(LinkType).where(LinkType.namespace_id == namespace.id, LinkType.api_name == payload.api_name),
    )
    if existing:
        return existing
    decision = policy_service.authorize(session, context, "create", "link_type", namespace.id)
    return registry_service.create_link_type(session, payload, context, decision)


def seed_employee_domain(session: Session) -> dict[str, str]:
    context = seed_context()
    workspace = ensure_workspace(session, context)
    namespace = ensure_namespace(session, workspace, context)
    source = ensure_source(session, namespace, context)

    employees = ensure_table(
        session,
        namespace,
        source,
        context,
        DatasetTableCreate(
            namespace_id=namespace.id,
            source_system_id=source.id,
            api_name="hr_employees",
            schema_name="public",
            table_name="employees",
            physical_name="public.employees",
            description="Employee source table",
            primary_key_columns=["employee_id"],
            classification_tags=["internal", "pii"],
            allowed_purposes=["payroll", "workforce_planning"],
            owner_group="hr-data-owners",
            steward_group="hr-data-stewards",
            columns=[
                DatasetColumnCreate(column_name="employee_id", data_type="string", nullable=False, ordinal_position=1),
                DatasetColumnCreate(column_name="full_name", data_type="string", nullable=False, ordinal_position=2),
                DatasetColumnCreate(
                    column_name="email_address",
                    data_type="string",
                    nullable=False,
                    ordinal_position=3,
                    classification_tags=["pii"],
                ),
                DatasetColumnCreate(column_name="department_id", data_type="string", nullable=False, ordinal_position=4),
                DatasetColumnCreate(column_name="employment_status", data_type="string", nullable=False, ordinal_position=5),
                DatasetColumnCreate(column_name="hire_date", data_type="date", nullable=True, ordinal_position=6),
            ],
        ),
    )
    departments = ensure_table(
        session,
        namespace,
        source,
        context,
        DatasetTableCreate(
            namespace_id=namespace.id,
            source_system_id=source.id,
            api_name="hr_departments",
            schema_name="public",
            table_name="departments",
            physical_name="public.departments",
            description="Department source table",
            primary_key_columns=["department_id"],
            classification_tags=["internal"],
            allowed_purposes=["payroll", "workforce_planning"],
            columns=[
                DatasetColumnCreate(column_name="department_id", data_type="string", nullable=False, ordinal_position=1),
                DatasetColumnCreate(column_name="name", data_type="string", nullable=False, ordinal_position=2),
                DatasetColumnCreate(column_name="cost_center", data_type="string", nullable=True, ordinal_position=3),
            ],
        ),
    )
    projects = ensure_table(
        session,
        namespace,
        source,
        context,
        DatasetTableCreate(
            namespace_id=namespace.id,
            source_system_id=source.id,
            api_name="hr_projects",
            schema_name="public",
            table_name="projects",
            physical_name="public.projects",
            description="Project source table",
            primary_key_columns=["project_id"],
            classification_tags=["internal"],
            allowed_purposes=["workforce_planning"],
            columns=[
                DatasetColumnCreate(column_name="project_id", data_type="string", nullable=False, ordinal_position=1),
                DatasetColumnCreate(column_name="name", data_type="string", nullable=False, ordinal_position=2),
                DatasetColumnCreate(column_name="status", data_type="string", nullable=False, ordinal_position=3),
            ],
        ),
    )
    assignments = ensure_table(
        session,
        namespace,
        source,
        context,
        DatasetTableCreate(
            namespace_id=namespace.id,
            source_system_id=source.id,
            api_name="hr_employee_project_assignments",
            schema_name="public",
            table_name="employee_project_assignments",
            physical_name="public.employee_project_assignments",
            description="Many-to-many Employee to Project assignment table",
            primary_key_columns=["employee_id", "project_id"],
            classification_tags=["internal"],
            allowed_purposes=["workforce_planning"],
            columns=[
                DatasetColumnCreate(column_name="employee_id", data_type="string", nullable=False, ordinal_position=1),
                DatasetColumnCreate(column_name="project_id", data_type="string", nullable=False, ordinal_position=2),
                DatasetColumnCreate(column_name="allocation_percent", data_type="integer", nullable=True, ordinal_position=3),
            ],
        ),
    )

    employee_object = ensure_object_type(
        session,
        namespace,
        context,
        ObjectTypeCreate(
            namespace_id=namespace.id,
            dataset_table_id=employees.id,
            api_name="Employee",
            display_name="Employee",
            description="A worker employed by the organization",
            primary_key_property="employeeId",
            status="active",
            classification_tags=["internal", "pii"],
            allowed_purposes=["payroll", "workforce_planning"],
            owner_group="hr-data-owners",
            steward_group="hr-data-stewards",
        ),
        [
            ObjectPropertyCreate(api_name="employeeId", display_name="Employee ID", data_type="string", source_column_name="employee_id", required=True, is_primary_key=True),
            ObjectPropertyCreate(api_name="fullName", display_name="Full Name", data_type="string", source_column_name="full_name", required=True, classification_tags=["pii"]),
            ObjectPropertyCreate(api_name="emailAddress", display_name="Email Address", data_type="string", source_column_name="email_address", required=True, classification_tags=["pii"]),
            ObjectPropertyCreate(api_name="departmentId", display_name="Department ID", data_type="string", source_column_name="department_id", required=True),
            ObjectPropertyCreate(api_name="employmentStatus", display_name="Employment Status", data_type="string", source_column_name="employment_status", required=True),
            ObjectPropertyCreate(api_name="hireDate", display_name="Hire Date", data_type="date", source_column_name="hire_date"),
        ],
    )
    department_object = ensure_object_type(
        session,
        namespace,
        context,
        ObjectTypeCreate(
            namespace_id=namespace.id,
            dataset_table_id=departments.id,
            api_name="Department",
            display_name="Department",
            description="Organizational department",
            primary_key_property="departmentId",
            status="active",
            classification_tags=["internal"],
            allowed_purposes=["payroll", "workforce_planning"],
        ),
        [
            ObjectPropertyCreate(api_name="departmentId", display_name="Department ID", data_type="string", source_column_name="department_id", required=True, is_primary_key=True),
            ObjectPropertyCreate(api_name="name", display_name="Name", data_type="string", source_column_name="name", required=True),
            ObjectPropertyCreate(api_name="costCenter", display_name="Cost Center", data_type="string", source_column_name="cost_center"),
        ],
    )
    project_object = ensure_object_type(
        session,
        namespace,
        context,
        ObjectTypeCreate(
            namespace_id=namespace.id,
            dataset_table_id=projects.id,
            api_name="Project",
            display_name="Project",
            description="Internal project or program",
            primary_key_property="projectId",
            status="active",
            classification_tags=["internal"],
            allowed_purposes=["workforce_planning"],
        ),
        [
            ObjectPropertyCreate(api_name="projectId", display_name="Project ID", data_type="string", source_column_name="project_id", required=True, is_primary_key=True),
            ObjectPropertyCreate(api_name="name", display_name="Name", data_type="string", source_column_name="name", required=True),
            ObjectPropertyCreate(api_name="status", display_name="Status", data_type="string", source_column_name="status", required=True),
        ],
    )

    employee_department_link = ensure_link(
        session,
        namespace,
        context,
        LinkTypeCreate(
            namespace_id=namespace.id,
            api_name="EmployeeBelongsToDepartment",
            display_name="Employee Belongs To Department",
            source_object_type_id=employee_object.id,
            target_object_type_id=department_object.id,
            cardinality="many_to_one",
            join_type="foreign_key",
            source_property_api_name="departmentId",
            target_property_api_name="departmentId",
            description="Connects each employee to their department",
            status="active",
            classification_tags=["internal"],
            allowed_purposes=["payroll", "workforce_planning"],
        ),
    )
    employee_project_link = ensure_link(
        session,
        namespace,
        context,
        LinkTypeCreate(
            namespace_id=namespace.id,
            api_name="EmployeeAssignedToProject",
            display_name="Employee Assigned To Project",
            source_object_type_id=employee_object.id,
            target_object_type_id=project_object.id,
            cardinality="many_to_many",
            join_type="join_table",
            source_property_api_name="employeeId",
            target_property_api_name="projectId",
            backing_dataset_table_id=assignments.id,
            description="Connects employees to projects through assignment rows",
            status="active",
            classification_tags=["internal"],
            allowed_purposes=["workforce_planning"],
        ),
    )

    return {
        "workspace_id": workspace.id,
        "namespace_id": namespace.id,
        "source_system_id": source.id,
        "employee_object_type_id": employee_object.id,
        "department_object_type_id": department_object.id,
        "project_object_type_id": project_object.id,
        "employee_department_link_type_id": employee_department_link.id,
        "employee_project_link_type_id": employee_project_link.id,
    }


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        result = seed_employee_domain(session)
    # Log only the asset labels and a count, not the identifier values. The seed
    # creates a source system carrying a connection URI, so the resulting records
    # are treated as sensitive; printing their values would write that to logs.
    print(f"Seeded Employee domain: created {len(result)} assets.")
    print("Assets: " + ", ".join(sorted(result.keys())))


if __name__ == "__main__":
    main()
