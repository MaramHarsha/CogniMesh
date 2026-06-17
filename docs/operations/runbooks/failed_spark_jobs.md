# Runbook: Failed Spark Jobs

## Symptoms
- `compute-control` reports SQL or custom python transform jobs failing with status `FAILED`.
- Downstream datasets are not populated.

## Triage
1. **Check compute run logs**:
   ```bash
   docker compose logs compute-control --tail=100
   ```
2. **Review Spark driver logs**:
   If running on Kubernetes, inspect Spark executor pods:
   ```bash
   kubectl logs -n cognimesh -l spark-role=driver
   ```
3. **Verify memory limits**:
   Ensure Spark executor did not fail due to OutOfMemory (OOM) or container eviction.

## Remediation
1. **Optimize partition count**:
   If failing due to skewed datasets or partition memory limits, adjust partition size parameter in the pipeline transform config.
2. **Re-run Spark job**:
   Resubmit the job using `pipeline-control` run endpoint.
3. **Verify Nessie catalog reference**:
   Ensure Nessie transaction branch has not drifted or been deleted during job execution.
