// Data layer for the CogniMesh Console.
//
// Object *type* metadata is fetched live from the Object Registry (proxied at
// /api/registry, see vite.config.ts) and falls back to mock data when the
// backend is unreachable. Object *instances* are served from a structured mock
// dataset; swapping these to the Object Query Service later is a single-function
// change in queryObjects()/getObject().

export type BadgeKind = 'green' | 'gray' | 'purple' | 'blue';

export interface ObjectTypeSummary {
  object_type_id: string;
  namespace: string;
  api_name: string;
  display_name: string;
  description: string;
  status: string;
}

export interface ObjectColumn {
  key: string;
  label: string;
  mono?: boolean;
}

export interface ObjectProperty {
  name: string;
  value: string;
  badge?: BadgeKind;
}

export interface ObjectRelationship {
  link_type: string;
  target: string;
}

export interface ObjectRecord {
  id: string;
  title: string;
  summary: Record<string, string>;
  properties: ObjectProperty[];
  relationships: ObjectRelationship[];
  governance: { classification: string; purpose: string; quality: string };
}

export interface ObjectTypeData {
  columns: ObjectColumn[];
  records: ObjectRecord[];
}

export function statusBadge(status: string): BadgeKind {
  return status.toLowerCase() === 'active' ? 'green' : 'gray';
}

// ----------------------------------------------------------------- mock data

const MOCK_OBJECT_TYPES: ObjectTypeSummary[] = [
  { object_type_id: 'ot_employee', namespace: 'hr', api_name: 'Employee', display_name: 'Employee', description: 'Represents a person employed by the organization.', status: 'active' },
  { object_type_id: 'ot_department', namespace: 'hr', api_name: 'Department', display_name: 'Department', description: 'An organizational unit containing employees.', status: 'active' },
  { object_type_id: 'ot_project', namespace: 'operations', api_name: 'Project', display_name: 'Project', description: 'A bounded initiative with assigned employees.', status: 'draft' },
];

const MOCK_DATA: Record<string, ObjectTypeData> = {
  Employee: {
    columns: [
      { key: 'id', label: 'ID', mono: true },
      { key: 'fullName', label: 'Full Name' },
      { key: 'department', label: 'Department' },
      { key: 'status', label: 'Status' },
    ],
    records: [
      {
        id: 'emp_001', title: 'Alice Smith',
        summary: { fullName: 'Alice Smith', department: 'Engineering', status: 'ACTIVE' },
        properties: [
          { name: 'emailAddress', value: 'alice.smith@example.com' },
          { name: 'employmentStatus', value: 'ACTIVE', badge: 'green' },
          { name: 'hireDate', value: '2024-01-15' },
          { name: 'costCenter', value: 'ENG-409' },
        ],
        relationships: [
          { link_type: 'BelongsToDepartment', target: 'Engineering' },
          { link_type: 'AssignedToProject', target: 'Project Phoenix' },
        ],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '100% Passes' },
      },
      {
        id: 'emp_002', title: 'Bob Johnson',
        summary: { fullName: 'Bob Johnson', department: 'Sales', status: 'ACTIVE' },
        properties: [
          { name: 'emailAddress', value: 'bob.johnson@example.com' },
          { name: 'employmentStatus', value: 'ACTIVE', badge: 'green' },
          { name: 'hireDate', value: '2023-06-02' },
          { name: 'costCenter', value: 'SAL-110' },
        ],
        relationships: [{ link_type: 'BelongsToDepartment', target: 'Sales' }],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '100% Passes' },
      },
      {
        id: 'emp_003', title: 'Charlie Lee',
        summary: { fullName: 'Charlie Lee', department: 'Marketing', status: 'ON_LEAVE' },
        properties: [
          { name: 'emailAddress', value: 'charlie.lee@example.com' },
          { name: 'employmentStatus', value: 'ON_LEAVE', badge: 'gray' },
          { name: 'hireDate', value: '2022-11-20' },
          { name: 'costCenter', value: 'MKT-200' },
        ],
        relationships: [{ link_type: 'BelongsToDepartment', target: 'Marketing' }],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '98% Passes' },
      },
      {
        id: 'emp_004', title: 'Diana Prince',
        summary: { fullName: 'Diana Prince', department: 'Engineering', status: 'ACTIVE' },
        properties: [
          { name: 'emailAddress', value: 'diana.prince@example.com' },
          { name: 'employmentStatus', value: 'ACTIVE', badge: 'green' },
          { name: 'hireDate', value: '2021-03-08' },
          { name: 'costCenter', value: 'ENG-409' },
        ],
        relationships: [
          { link_type: 'BelongsToDepartment', target: 'Engineering' },
          { link_type: 'AssignedToProject', target: 'Project Phoenix' },
        ],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '100% Passes' },
      },
      {
        id: 'emp_005', title: 'Evan Wright',
        summary: { fullName: 'Evan Wright', department: 'HR', status: 'ACTIVE' },
        properties: [
          { name: 'emailAddress', value: 'evan.wright@example.com' },
          { name: 'employmentStatus', value: 'ACTIVE', badge: 'green' },
          { name: 'hireDate', value: '2020-09-14' },
          { name: 'costCenter', value: 'HRG-050' },
        ],
        relationships: [{ link_type: 'BelongsToDepartment', target: 'HR' }],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '100% Passes' },
      },
    ],
  },
  Department: {
    columns: [
      { key: 'id', label: 'ID', mono: true },
      { key: 'name', label: 'Name' },
      { key: 'costCenter', label: 'Cost Center' },
      { key: 'headcount', label: 'Headcount' },
    ],
    records: [
      {
        id: 'dep_eng', title: 'Engineering',
        summary: { name: 'Engineering', costCenter: 'ENG-409', headcount: '2' },
        properties: [
          { name: 'departmentName', value: 'Engineering' },
          { name: 'costCenter', value: 'ENG-409' },
          { name: 'headcount', value: '2' },
        ],
        relationships: [{ link_type: 'HasEmployee', target: 'Alice Smith' }, { link_type: 'HasEmployee', target: 'Diana Prince' }],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '100% Passes' },
      },
      {
        id: 'dep_sales', title: 'Sales',
        summary: { name: 'Sales', costCenter: 'SAL-110', headcount: '1' },
        properties: [
          { name: 'departmentName', value: 'Sales' },
          { name: 'costCenter', value: 'SAL-110' },
          { name: 'headcount', value: '1' },
        ],
        relationships: [{ link_type: 'HasEmployee', target: 'Bob Johnson' }],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '100% Passes' },
      },
      {
        id: 'dep_mkt', title: 'Marketing',
        summary: { name: 'Marketing', costCenter: 'MKT-200', headcount: '1' },
        properties: [
          { name: 'departmentName', value: 'Marketing' },
          { name: 'costCenter', value: 'MKT-200' },
          { name: 'headcount', value: '1' },
        ],
        relationships: [{ link_type: 'HasEmployee', target: 'Charlie Lee' }],
        governance: { classification: 'Internal', purpose: 'Workforce Planning', quality: '98% Passes' },
      },
    ],
  },
  Project: {
    columns: [
      { key: 'id', label: 'ID', mono: true },
      { key: 'name', label: 'Name' },
      { key: 'lead', label: 'Lead' },
      { key: 'status', label: 'Status' },
    ],
    records: [
      {
        id: 'prj_phoenix', title: 'Project Phoenix',
        summary: { name: 'Project Phoenix', lead: 'Diana Prince', status: 'ACTIVE' },
        properties: [
          { name: 'projectName', value: 'Project Phoenix' },
          { name: 'lead', value: 'Diana Prince' },
          { name: 'status', value: 'ACTIVE', badge: 'green' },
          { name: 'startDate', value: '2025-02-01' },
        ],
        relationships: [{ link_type: 'AssignedEmployee', target: 'Alice Smith' }, { link_type: 'AssignedEmployee', target: 'Diana Prince' }],
        governance: { classification: 'Confidential', purpose: 'Delivery', quality: '100% Passes' },
      },
      {
        id: 'prj_atlas', title: 'Project Atlas',
        summary: { name: 'Project Atlas', lead: 'Bob Johnson', status: 'DRAFT' },
        properties: [
          { name: 'projectName', value: 'Project Atlas' },
          { name: 'lead', value: 'Bob Johnson' },
          { name: 'status', value: 'DRAFT', badge: 'gray' },
          { name: 'startDate', value: '2025-08-15' },
        ],
        relationships: [{ link_type: 'AssignedEmployee', target: 'Bob Johnson' }],
        governance: { classification: 'Confidential', purpose: 'Delivery', quality: 'Pending' },
      },
    ],
  },
};

// ----------------------------------------------------------------- live API

interface RegistryObjectType {
  id: string;
  namespace_id: string;
  api_name: string;
  display_name: string;
  description: string | null;
  status: string;
}

interface RegistryNamespace {
  id: string;
  api_name: string;
}

const REGISTRY_BASE = '/api/registry';

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Request to ${url} failed: ${res.status}`);
  return (await res.json()) as T;
}

/** Live object types from the Object Registry, with namespace names resolved. */
export async function fetchObjectTypes(): Promise<{ data: ObjectTypeSummary[]; live: boolean }> {
  try {
    const [types, namespaces] = await Promise.all([
      getJson<RegistryObjectType[]>(`${REGISTRY_BASE}/v1/object-types`),
      getJson<RegistryNamespace[]>(`${REGISTRY_BASE}/v1/namespaces`).catch(() => [] as RegistryNamespace[]),
    ]);
    if (!Array.isArray(types) || types.length === 0) throw new Error('no object types');
    const nsById = new Map(namespaces.map((ns) => [ns.id, ns.api_name]));
    const data = types.map((t) => ({
      object_type_id: t.id,
      namespace: nsById.get(t.namespace_id) ?? t.namespace_id,
      api_name: t.api_name,
      display_name: t.display_name,
      description: t.description ?? '',
      status: t.status,
    }));
    return { data, live: true };
  } catch {
    return { data: MOCK_OBJECT_TYPES, live: false };
  }
}

/** Rows for an object type, filtered by a free-text search across summary values. */
export function queryObjects(apiName: string, search: string): ObjectTypeData {
  const typeData = MOCK_DATA[apiName] ?? MOCK_DATA.Employee;
  const term = search.trim().toLowerCase();
  if (!term) return typeData;
  const records = typeData.records.filter((record) => {
    const haystack = [record.id, ...Object.values(record.summary)].join(' ').toLowerCase();
    return haystack.includes(term);
  });
  return { columns: typeData.columns, records };
}

/** A single object instance by type + id. */
export function getObject(apiName: string, id: string): ObjectRecord | undefined {
  const typeData = MOCK_DATA[apiName] ?? MOCK_DATA.Employee;
  return typeData.records.find((record) => record.id === id);
}

/** The namespace an object type belongs to (for breadcrumb/badge display). */
export function namespaceForType(apiName: string): string {
  return MOCK_OBJECT_TYPES.find((type) => type.api_name === apiName)?.namespace ?? 'default';
}

/** Aggregated metrics for the Analytics view. */
export interface AnalyticsSummary {
  totalObjectTypes: number;
  totalInstances: number;
  employeesByDepartment: { label: string; value: number }[];
  statusBreakdown: { label: string; value: number }[];
}

export function getAnalytics(): AnalyticsSummary {
  const employees = MOCK_DATA.Employee.records;
  const byDept = new Map<string, number>();
  const byStatus = new Map<string, number>();
  for (const emp of employees) {
    byDept.set(emp.summary.department, (byDept.get(emp.summary.department) ?? 0) + 1);
    byStatus.set(emp.summary.status, (byStatus.get(emp.summary.status) ?? 0) + 1);
  }
  const totalInstances = Object.values(MOCK_DATA).reduce((sum, t) => sum + t.records.length, 0);
  return {
    totalObjectTypes: MOCK_OBJECT_TYPES.length,
    totalInstances,
    employeesByDepartment: [...byDept.entries()].map(([label, value]) => ({ label, value })),
    statusBreakdown: [...byStatus.entries()].map(([label, value]) => ({ label, value })),
  };
}
