import os
import streamlit as st
import pandas as pd
from cognimesh import CogniMeshClient

# 1. Custom premium dark theme styling
st.set_page_config(
    page_title="CogniMesh Low-Code App Hub",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply sleek modern styling custom CSS
st.markdown("""
<style>
    /* Sleek gradient and typography */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #f8fafc;
    }
    
    /* Header card styled */
    .header-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(99, 102, 241, 0.2);
        backdrop-filter: blur(12px);
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
    }
    
    .header-title {
        color: #818cf8;
        font-size: 32px;
        font-weight: 700;
        margin: 0;
    }
    
    .header-subtitle {
        color: #94a3b8;
        font-size: 16px;
        margin: 8px 0 0 0;
    }

    /* Status badge colors */
    .status-badge-active {
        background-color: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }
    
    .status-badge-draft {
        background-color: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# 2. Sidebar configuration and client initialization
st.sidebar.title("🕸️ CogniMesh Hub")
st.sidebar.markdown("Configure endpoints and user contexts below.")

query_url = st.sidebar.text_input("Object Query Service URL", value="http://localhost:8060")
app_control_url = st.sidebar.text_input("App Control Service URL", value="http://localhost:8090")

st.sidebar.subheader("Developer Credentials")
actor = st.sidebar.text_input("Actor ID", value="dev_user_1")
roles_str = st.sidebar.text_input("Roles (comma separated)", value="platform_admin,data_engineer")
workspace = st.sidebar.text_input("Workspace ID", value="ws-default")
purpose = st.sidebar.selectbox("Data Purpose", ["analytics", "operations", "compliance", "support"])

roles = [r.strip() for r in roles_str.split(",") if r.strip()]

# Create the CogniMesh SDK Client
client = CogniMeshClient(
    query_service_url=query_url,
    app_control_url=app_control_url,
    actor=actor,
    roles=roles,
    purpose=purpose,
    workspace_id=workspace
)

# 3. Main Dashboard Header
st.markdown("""
<div class="header-card">
    <h1 class="header-title">Low-Code App Hub & Explorer</h1>
    <p class="header-subtitle">Manage registered low-code data apps, deploy compliant interfaces, and query the Semantic Object Layer.</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🚀 App Registry & Deployment", "🔍 Object Explorer", "📋 Compliance & Audits"])

# --- TAB 1: App Registry & Deployment ---
with tab1:
    st.subheader("Registered Low-Code Applications")
    
    # Fetch apps list
    try:
        apps = client.list_apps(workspace_id=workspace)
        if apps:
            df_apps = pd.DataFrame(apps)
            # Reorder columns for display
            display_cols = ["id", "name", "purpose", "owner", "status", "created_at"]
            st.dataframe(df_apps[display_cols], use_container_width=True)
            
            # Action controls for deployment
            st.markdown("---")
            col1, col2 = st.columns([1, 2])
            with col1:
                app_to_deploy = st.selectbox("Select App to Deploy / Verify", options=[app["id"] for app in apps])
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Verify & Deploy Application"):
                    with st.spinner("Executing compliance policy evaluation..."):
                        deploy_res = client.deploy_app(app_to_deploy)
                        if deploy_res["satisfied"]:
                            st.success(f"🎉 Deployment Successful! Status: ACTIVE. {deploy_res['message']}")
                        else:
                            st.error(f"❌ Deployment Rejected! {deploy_res['message']}")
                            for err in deploy_res["errors"]:
                                st.warning(f"- {err}")
        else:
            st.info("No applications registered in this workspace yet.")
    except Exception as e:
        st.error(f"Failed to fetch application registry: {e}")
        st.info("Ensure the app-control service is running and accessible.")

    # Register New App Form
    st.markdown("---")
    with st.expander("➕ Register a New Low-Code Application", expanded=False):
        with st.form("register_app_form"):
            app_name = st.text_input("Application Name", placeholder="Employee Compensation Portal")
            app_purpose = st.text_input("Application Purpose", value="hr-reporting")
            app_owner = st.text_input("Owner Email / ID", value=actor)
            deps_str = st.text_input("Data Dependencies (comma separated)", value="Employee, Department")
            deploy_url = st.text_input("Deployment Target URL (Optional)", placeholder="http://appsmith.mycompany/hr-portal")
            
            app_deps = [d.strip() for d in deps_str.split(",") if d.strip()]
            
            submit = st.form_submit_button("Register Application")
            if submit:
                if not app_name or not app_purpose:
                    st.error("Name and Purpose are required fields.")
                else:
                    try:
                        new_app = client.register_app(
                            name=app_name,
                            workspace_id=workspace,
                            purpose=app_purpose,
                            owner=app_owner,
                            data_dependencies=app_deps,
                            deployment_url=deploy_url
                        )
                        st.success(f"App successfully registered with ID: {new_app['id']} in DRAFT mode.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Registration failed: {e}")

# --- TAB 2: Object Explorer ---
with tab2:
    st.subheader("Query Semantic Object Layer")
    
    col_type, col_search, col_limit = st.columns([1, 2, 1])
    with col_type:
        object_type = st.text_input("Object Type Name", value="Employee")
    with col_search:
        search_query = st.text_input("Full-text Search", placeholder="e.g. John")
    with col_limit:
        limit = st.number_input("Limit Results", min_value=1, max_value=500, value=20)
        
    st.markdown("##### Filter Conditions")
    col_prop, col_op, col_val = st.columns(3)
    with col_prop:
        filter_prop = st.text_input("Property", placeholder="employmentStatus")
    with col_op:
        filter_op = st.selectbox("Operator", ["eq", "neq", "gt", "gte", "lt", "lte", "contains"])
    with col_val:
        filter_val = st.text_input("Value", placeholder="ACTIVE")

    # Optional active app selection for audit linking
    st.markdown("---")
    col_audit_app, = st.columns(1)
    try:
        apps = client.list_apps(workspace_id=workspace)
        audit_app_id = col_audit_app.selectbox("Context App (for Audit Compliance)", options=["None"] + [app["id"] for app in apps])
    except Exception:
        audit_app_id = "None"
        col_audit_app.info("App Control offline. Audit logs will not be written.")

    if st.button("Execute Semantic Query", type="primary"):
        with st.spinner("Fetching data from Semantic Object Layer..."):
            try:
                # Build query fluently
                query_builder = client.objects(object_type).select().limit(limit)
                
                if search_query:
                    query_builder.search(search_query)
                    
                if filter_prop and filter_val:
                    # Parse numerical if applicable
                    val = filter_val
                    try:
                        if "." in filter_val:
                            val = float(filter_val)
                        else:
                            val = int(filter_val)
                    except ValueError:
                        pass
                    
                    if filter_op == "eq":
                        query_builder.where(filter_prop, val)
                    else:
                        query_builder.where(filter_prop, **{filter_op: val})
                
                # Execute
                result = query_builder.execute()
                rows = result.get("rows", [])
                
                if rows:
                    df = pd.DataFrame(rows)
                    st.success(f"Retrieved {result.get('row_count', len(rows))} records (Cache: {'HIT' if result.get('cache', {}).get('hit') else 'MISS'}).")
                    st.dataframe(df, use_container_width=True)
                    
                    # Log Audit to App Registry automatically if App Context is supplied
                    if audit_app_id != "None":
                        audit_res = client.log_audit(
                            app_id=audit_app_id,
                            user_id=actor,
                            operation="QUERY_OBJECTS",
                            asset_id=f"object_{object_type.lower()}",
                            purpose=purpose,
                            details={
                                "filter_property": filter_prop,
                                "search_query": search_query,
                                "row_count_accessed": len(rows),
                                "audit_record_id": result.get("audit_id", "N/A")
                            }
                        )
                        st.info(f"🛡️ Compliance Audit Record logged successfully with ID: {audit_res['id']}")
                else:
                    st.info("No matching records found.")
            except Exception as e:
                st.error(f"Query Execution Failed: {e}")

# --- TAB 3: Compliance & Audits ---
with tab3:
    st.subheader("Compliance Audit Logs")
    
    try:
        apps = client.list_apps(workspace_id=workspace)
        if apps:
            app_id_audit = st.selectbox("Select App to View Logs", options=[app["id"] for app in apps])
            
            if st.button("Fetch Compliance Logs"):
                with st.spinner("Retrieving audit trail..."):
                    audits = client.list_audits(app_id_audit)
                    if audits:
                        df_audits = pd.DataFrame(audits)
                        st.dataframe(df_audits[["id", "user_id", "operation", "asset_id", "purpose", "details", "created_at"]], use_container_width=True)
                    else:
                        st.info("No audit logs recorded for this application yet.")
        else:
            st.info("No applications registered to audit.")
    except Exception as e:
        st.error(f"Failed to fetch audit logs: {e}")
