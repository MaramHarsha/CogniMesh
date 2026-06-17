import { test, mock } from "node:test";
import assert from "node:assert";
import { CogniMeshClient, ObjectQueryBuilder } from "../src/client";

test("ObjectQueryBuilder serialization", () => {
  const client = new CogniMeshClient({ actor: "user1", roles: ["admin"] });
  const builder = client
    .objects("Employee")
    .select("id", "name", "salary")
    .where("status", "ACTIVE")
    .where("salary", null, { gte: 100000 })
    .limit(10)
    .offset(5)
    .orderBy("salary", "desc")
    .search("John");

  const payload = builder.toDict();

  assert.strictEqual(payload.from, "Employee");
  assert.deepStrictEqual(payload.select, ["id", "name", "salary"]);
  assert.deepStrictEqual(payload.where, {
    status: "ACTIVE",
    salary: { gte: 100000 },
  });
  assert.strictEqual(payload.limit, 10);
  assert.strictEqual(payload.offset, 5);
  assert.deepStrictEqual(payload.orderBy, [{ property: "salary", direction: "desc" }]);
  assert.strictEqual(payload.search, "John");
});

test("CogniMeshClient execute_query mock fetch", async (t) => {
  const client = new CogniMeshClient({
    queryServiceUrl: "http://mock-query-service",
    actor: "dev-user",
    roles: ["data_engineer"],
    purpose: "hr-review",
    workspaceId: "ws-99",
  });

  const mockResponse = { rows: [{ id: "emp_1" }], row_count: 1 };

  // Mock global fetch
  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const fetchMock = mock.fn(async (url: any, options: any) => {
    assert.strictEqual(url, "http://mock-query-service/v1/query/objects");
    assert.strictEqual(options.method, "POST");
    
    const body = JSON.parse(options.body);
    assert.strictEqual(body.from, "Employee");
    assert.deepStrictEqual(body.select, ["id"]);

    const headers = options.headers;
    assert.strictEqual(headers["X-CogniMesh-Actor"], "dev-user");
    assert.strictEqual(headers["X-CogniMesh-Roles"], "data_engineer");
    assert.strictEqual(headers["X-CogniMesh-Purpose"], "hr-review");
    assert.strictEqual(headers["X-CogniMesh-Workspace"], "ws-99");

    return {
      ok: true,
      status: 200,
      json: async () => mockResponse,
    } as Response;
  });

  globalThis.fetch = fetchMock;

  const result = await client.objects("Employee").select("id").execute();

  assert.strictEqual(result.row_count, 1);
  assert.strictEqual(result.rows[0].id, "emp_1");
  assert.strictEqual(fetchMock.mock.callCount(), 1);
});

test("CogniMeshClient register_app mock fetch", async (t) => {
  const client = new CogniMeshClient({
    appControlUrl: "http://mock-app-control",
    actor: "dev-user",
    roles: ["data_engineer"],
  });

  const mockResponse = { id: "capp_123", status: "draft" };

  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const fetchMock = mock.fn(async (url: any, options: any) => {
    assert.strictEqual(url, "http://mock-app-control/v1/apps");
    assert.strictEqual(options.method, "POST");

    const body = JSON.parse(options.body);
    assert.strictEqual(body.name, "Dashboard");
    assert.strictEqual(body.workspace_id, "ws-99");
    assert.strictEqual(body.purpose, "analytics");
    assert.deepStrictEqual(body.data_dependencies, ["Employee"]);

    return {
      ok: true,
      status: 201,
      json: async () => mockResponse,
    } as Response;
  });

  globalThis.fetch = fetchMock;

  const res = await client.register_app(
    "Dashboard",
    "ws-99",
    "analytics",
    "dev-user",
    ["Employee"]
  );

  assert.strictEqual(res.id, "capp_123");
  assert.strictEqual(fetchMock.mock.callCount(), 1);
});

test("CogniMeshClient registry and actions mock fetch", async (t) => {
  const client = new CogniMeshClient({
    objectRegistryUrl: "http://mock-registry",
    actionControlUrl: "http://mock-action",
  });

  const originalFetch = globalThis.fetch;
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const fetchMock = mock.fn(async (url: any, options: any) => {
    if (url.includes("object-types")) {
      return {
        ok: true,
        status: 201,
        json: async () => ({ id: "obj_1" }),
      } as Response;
    } else if (url.includes("actions")) {
      return {
        ok: true,
        status: 201,
        json: async () => ({ id: "sub_1" }),
      } as Response;
    }
    return { ok: false, status: 400 } as Response;
  });

  globalThis.fetch = fetchMock;

  const regRes = await client.register_object_type({ api_name: "Employee" });
  assert.strictEqual(regRes.id, "obj_1");

  const actRes = await client.submit_action({ action_type: "create_employee" });
  assert.strictEqual(actRes.id, "sub_1");
});
