# Streamlit Dashboard Example using CogniMesh Python SDK

This is a sample operational dashboard built with [Streamlit](https://streamlit.io/) that integrates with the CogniMesh Object Query Service (OQS) and App Registry Control Plane using the official `cognimesh-sdk`.

## Prerequisites

Ensure you have Python 3.12+ installed, along with Streamlit:

```bash
pip install streamlit pandas
pip install -e packages/sdk-python
```

## Running the App

Run the following command from the root directory of the repository:

```bash
streamlit run apps/streamlit-examples/app.py
```

## Features Demonstrated

1. **Service Configuration & Context Handshake**: Setup endpoints and authentication headers dynamically in the sidebar.
2. **Dynamic Query Building**: Use the SDK's fluent builder to query the `Employee` object type, apply filters, and search.
3. **App Registry Integration**: View registered apps, register a new low-code app, run validation checks, and view deployment status.
4. **Interactive Audit Log Viewer**: Read and filter historical logs for registered applications.
