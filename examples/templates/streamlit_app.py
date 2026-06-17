# Streamlit reference dashboard demo app
import streamlit as st
import json
import httpx

st.title("CogniMesh Analytics Console")

st.sidebar.header("Configuration")
actor = st.sidebar.text_input("Actor", value="data_engineer")
purpose = st.sidebar.text_input("Purpose", value="analytics")

st.write("### Query Objects")
object_type = st.selectbox("Object Type", ["Employee", "Order", "Shipment"])

headers = {
    "X-CogniMesh-Actor": actor,
    "X-CogniMesh-Purpose": purpose,
    "X-CogniMesh-Roles": "data_engineer,analyst",
}

if st.button("Fetch Objects"):
    payload = {
        "from": object_type,
        "select": [],
        "where": {},
        "offset": 0
    }
    
    try:
        res = httpx.post("http://localhost:8060/v1/query/objects", json=payload, headers=headers)
        if res.status_code == 200:
            st.success("Successfully fetched object instances")
            st.json(res.json())
        else:
            st.error(f"Error querying objects: {res.status_code} {res.text}")
    except Exception as e:
        st.error(f"Failed to connect to Object Query Service: {e}")
