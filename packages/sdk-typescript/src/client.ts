export class ObjectQueryBuilder {
  private _client: CogniMeshClient;
  private _objectType: string;
  private _select: string[] = [];
  private _where: Record<string, any> = {};
  private _limit: number | null = null;
  private _offset: number = 0;
  private _orderBy: Array<{ property: string; direction: "asc" | "desc" }> = [];
  private _search: string | null = null;

  constructor(client: CogniMeshClient, objectType: string) {
    this._client = client;
    this._objectType = objectType;
  }

  select(...properties: string[]): ObjectQueryBuilder {
    this._select.push(...properties);
    return this;
  }

  where(propertyName: string, value: any = null, operators?: Record<string, any>): ObjectQueryBuilder {
    if (value !== null && value !== undefined) {
      this._where[propertyName] = value;
    }
    if (operators) {
      if (!(propertyName in this._where)) {
        this._where[propertyName] = {};
      }
      if (typeof this._where[propertyName] === "object" && this._where[propertyName] !== null) {
        Object.assign(this._where[propertyName], operators);
      } else {
        this._where[propertyName] = operators;
      }
    }
    return this;
  }

  limit(limit: number): ObjectQueryBuilder {
    this._limit = limit;
    return this;
  }

  offset(offset: number): ObjectQueryBuilder {
    this._offset = offset;
    return this;
  }

  orderBy(propertyName: string, direction: "asc" | "desc" = "asc"): ObjectQueryBuilder {
    this._orderBy.push({ property: propertyName, direction });
    return this;
  }

  search(query: string): ObjectQueryBuilder {
    this._search = query;
    return this;
  }

  toDict(): Record<string, any> {
    const payload: Record<string, any> = {
      from: this._objectType,
      select: this._select,
      where: this._where,
      offset: this._offset,
    };
    if (this._limit !== null) {
      payload.limit = this._limit;
    }
    if (this._orderBy.length > 0) {
      payload.orderBy = this._orderBy;
    }
    if (this._search) {
      payload.search = this._search;
    }
    return payload;
  }

  execute(): Promise<any> {
    return this._client.execute_query(this.toDict());
  }
}

export interface CogniMeshClientOptions {
  queryServiceUrl?: string;
  appControlUrl?: string;
  objectRegistryUrl?: string;
  actionControlUrl?: string;
  pipelineControlUrl?: string;
  governanceControlUrl?: string;
  actor?: string;
  roles?: string[];
  purpose?: string;
  workspaceId?: string;
}

export class CogniMeshClient {
  public queryServiceUrl: string;
  public appControlUrl: string;
  public objectRegistryUrl: string;
  public actionControlUrl: string;
  public pipelineControlUrl: string;
  public governanceControlUrl: string;
  public actor?: string;
  public roles: string[];
  public purpose: string;
  public workspaceId?: string;

  constructor(options: CogniMeshClientOptions = {}) {
    this.queryServiceUrl = (options.queryServiceUrl || "http://localhost:8060").replace(/\/$/, "");
    this.appControlUrl = (options.appControlUrl || "http://localhost:8090").replace(/\/$/, "");
    this.objectRegistryUrl = (options.objectRegistryUrl || "http://localhost:8000").replace(/\/$/, "");
    this.actionControlUrl = (options.actionControlUrl || "http://localhost:8080").replace(/\/$/, "");
    this.pipelineControlUrl = (options.pipelineControlUrl || "http://localhost:8040").replace(/\/$/, "");
    this.governanceControlUrl = (options.governanceControlUrl || "http://localhost:8120").replace(/\/$/, "");
    this.actor = options.actor;
    this.roles = options.roles || [];
    this.purpose = options.purpose || "analytics";
    this.workspaceId = options.workspaceId;
  }

  getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.actor) {
      headers["X-CogniMesh-Actor"] = this.actor;
    }
    if (this.roles.length > 0) {
      headers["X-CogniMesh-Roles"] = this.roles.join(",");
    }
    if (this.purpose) {
      headers["X-CogniMesh-Purpose"] = this.purpose;
    }
    if (this.workspaceId) {
      headers["X-CogniMesh-Workspace"] = this.workspaceId;
    }
    return headers;
  }

  objects(objectType: string): ObjectQueryBuilder {
    return new ObjectQueryBuilder(this, objectType);
  }

  // --- Query API Operations

  async execute_query(queryPayload: Record<string, any>): Promise<any> {
    const url = `${this.queryServiceUrl}/v1/query/objects`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(queryPayload),
    });
    if (!res.ok) {
      throw new Error(`OQS error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  // --- App Control Plane API Operations

  async register_app(
    name: string,
    workspaceId: string,
    purpose: string,
    owner: string,
    dataDependencies: string[] = [],
    deploymentUrl?: string
  ): Promise<any> {
    const url = `${this.appControlUrl}/v1/apps`;
    const payload = {
      name,
      workspace_id: workspaceId,
      purpose,
      owner,
      data_dependencies: dataDependencies,
      deployment_url: deploymentUrl,
    };
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`App Registry error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async list_apps(workspaceId?: string): Promise<any[]> {
    let url = `${this.appControlUrl}/v1/apps`;
    if (workspaceId) {
      url += `?workspace_id=${encodeURIComponent(workspaceId)}`;
    }
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`App Registry list error: ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<any[]>;
  }

  async get_app(appId: string): Promise<any> {
    const url = `${this.appControlUrl}/v1/apps/${appId}`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`App Registry get error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async deploy_app(appId: string, environment: string = "production"): Promise<any> {
    const url = `${this.appControlUrl}/v1/apps/${appId}/deploy`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ environment }),
    });
    if (!res.ok) {
      throw new Error(`App deploy error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async log_audit(
    appId: string,
    userId: string,
    operation: string,
    assetId: string,
    purpose: string,
    details: Record<string, any> = {}
  ): Promise<any> {
    const url = `${this.appControlUrl}/v1/apps/${appId}/audit`;
    const payload = {
      user_id: userId,
      operation,
      asset_id: assetId,
      purpose,
      details,
    };
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Log audit error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async list_audits(appId: string): Promise<any[]> {
    const url = `${this.appControlUrl}/v1/apps/${appId}/audit`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`List audits error: ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<any[]>;
  }

  async register_component(
    apiName: string,
    displayName: string,
    objectType: string,
    propertiesMapped: string[],
    description?: string
  ): Promise<any> {
    const url = `${this.appControlUrl}/v1/apps/components`;
    const payload = {
      api_name: apiName,
      display_name: displayName,
      object_type: objectType,
      properties_mapped: propertiesMapped,
      description,
    };
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Register component error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async list_components(): Promise<any[]> {
    const url = `${this.appControlUrl}/v1/apps/components`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`List components error: ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<any[]>;
  }

  // --- Object Registry API Operations

  async register_object_type(payload: Record<string, any>): Promise<any> {
    const url = `${this.objectRegistryUrl}/v1/object-types`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Register object type error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async get_object_type(objectTypeId: string): Promise<any> {
    const url = `${this.objectRegistryUrl}/v1/object-types/${objectTypeId}`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Get object type error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async list_object_types(): Promise<any[]> {
    const url = `${this.objectRegistryUrl}/v1/object-types`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`List object types error: ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<any[]>;
  }

  // --- Action Control Plane API Operations

  async submit_action(payload: Record<string, any>): Promise<any> {
    const url = `${this.actionControlUrl}/v1/actions/submissions`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Submit action error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async get_action_submission(submissionId: string): Promise<any> {
    const url = `${this.actionControlUrl}/v1/actions/submissions/${submissionId}`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Get action submission error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  // --- Lineage Ledger API Operations

  async get_lineage(assetKind: string, assetId: string): Promise<any[]> {
    const url = `${this.objectRegistryUrl}/v1/lineage/${assetKind}/${assetId}`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Get lineage error: ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<any[]>;
  }

  async get_lineage_graph(assetKind: string, assetId: string): Promise<any> {
    const url = `${this.objectRegistryUrl}/v1/lineage/graph/${assetKind}/${assetId}`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Get lineage graph error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  // --- Pipeline Control API Operations

  async run_pipeline(pipelineId: string, payload: Record<string, any>): Promise<any> {
    const url = `${this.pipelineControlUrl}/v1/pipelines/${pipelineId}/runs`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Run pipeline error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }

  async get_pipeline_run(runId: string): Promise<any> {
    const url = `${this.pipelineControlUrl}/v1/pipelines/runs/${runId}`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Get pipeline run error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  }
}
