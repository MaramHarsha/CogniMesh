from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def evaluate_contract(contract: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Evaluates a single data quality contract against a list of rows (dictionaries).
    Returns a dictionary matching QualityCheckResult schema.
    """
    contract_id = contract["id"]
    contract_name = contract["name"]
    contract_type = contract["contract_type"]
    column_name = contract.get("column_name")
    config = contract.get("config") or {}

    result = {
        "contract_id": contract_id,
        "contract_name": contract_name,
        "contract_type": contract_type,
        "column_name": column_name,
        "status": "passed",
        "details": {},
    }

    try:
        if contract_type == "not_null":
            if not column_name:
                raise ValueError("column_name is required for not_null check")
            null_count = sum(1 for row in rows if row.get(column_name) is None)
            if null_count > 0:
                result["status"] = "failed"
            result["details"] = {"null_count": null_count, "total_rows": len(rows)}

        elif contract_type == "unique":
            if not column_name:
                raise ValueError("column_name is required for unique check")
            values = [row[column_name] for row in rows if row.get(column_name) is not None]
            unique_values = set(values)
            duplicate_count = len(values) - len(unique_values)
            if duplicate_count > 0:
                result["status"] = "failed"
            result["details"] = {"duplicate_count": duplicate_count, "total_values": len(values)}

        elif contract_type == "accepted_values":
            if not column_name:
                raise ValueError("column_name is required for accepted_values check")
            allowed = set(config.get("values") or [])
            if not allowed:
                raise ValueError("values list is required in config for accepted_values check")
            invalid_count = sum(
                1
                for row in rows
                if row.get(column_name) is not None and row[column_name] not in allowed
            )
            if invalid_count > 0:
                result["status"] = "failed"
            result["details"] = {"invalid_count": invalid_count, "allowed_values": sorted(list(allowed))}

        elif contract_type == "relationship_integrity":
            if not column_name:
                raise ValueError("column_name is required for relationship_integrity check")
            allowed = set(config.get("allowed_values") or [])
            # relationship integrity checks if values in column_name exist in the parent allowed_values
            invalid_count = sum(
                1
                for row in rows
                if row.get(column_name) is not None and row[column_name] not in allowed
            )
            if invalid_count > 0:
                result["status"] = "failed"
            result["details"] = {"missing_count": invalid_count}

        elif contract_type == "freshness":
            if not column_name:
                raise ValueError("column_name is required for freshness check")
            max_age_seconds = float(config.get("max_age_seconds") or 86400)
            now = datetime.now(timezone.utc)
            max_dt = None
            for row in rows:
                val = row.get(column_name)
                if val is not None:
                    try:
                        # parse ISO timestamp
                        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                        if max_dt is None or dt > max_dt:
                            max_dt = dt
                    except ValueError:
                        try:
                            # fallback to unix timestamp float
                            dt = datetime.fromtimestamp(float(val), tz=timezone.utc)
                            if max_dt is None or dt > max_dt:
                                max_dt = dt
                        except (ValueError, TypeError):
                            continue
            if max_dt is None:
                result["status"] = "failed"
                result["details"] = {"error": "No valid timestamps found in target column"}
            else:
                age = (now - max_dt).total_seconds()
                if age > max_age_seconds:
                    result["status"] = "failed"
                result["details"] = {
                    "max_age_seconds": max_age_seconds,
                    "actual_age_seconds": age,
                    "latest_timestamp": max_dt.isoformat(),
                }

        elif contract_type == "row_count_bounds":
            min_count = config.get("min")
            max_count = config.get("max")
            count = len(rows)
            passed = True
            if min_count is not None and count < int(min_count):
                passed = False
            if max_count is not None and count > int(max_count):
                passed = False
            if not passed:
                result["status"] = "failed"
            result["details"] = {"row_count": count, "min": min_count, "max": max_count}

        elif contract_type == "schema_match":
            expected_columns = config.get("columns") or {}
            if not expected_columns:
                raise ValueError("columns mapping is required in config for schema_match check")
            missing = []
            type_mismatches = []
            if rows:
                first_row = rows[0]
                for col, expected_type in expected_columns.items():
                    if col not in first_row:
                        missing.append(col)
                    else:
                        val = first_row[col]
                        if val is not None:
                            actual_type = type(val).__name__
                            # basic compatibility checks
                            if expected_type == "string" and not isinstance(val, (str, bytes)):
                                type_mismatches.append({"column": col, "expected": expected_type, "actual": actual_type})
                            elif expected_type == "integer" and not isinstance(val, int):
                                type_mismatches.append({"column": col, "expected": expected_type, "actual": actual_type})
                            elif expected_type == "float" and not isinstance(val, (int, float)):
                                type_mismatches.append({"column": col, "expected": expected_type, "actual": actual_type})
                            elif expected_type == "boolean" and not isinstance(val, bool):
                                type_mismatches.append({"column": col, "expected": expected_type, "actual": actual_type})
            else:
                # empty dataset - cannot verify types, just warn or fail if empty
                result["status"] = "failed"
                result["details"] = {"error": "Empty dataset cannot be verified for schema matching"}
                return result

            if missing or type_mismatches:
                result["status"] = "failed"
            result["details"] = {"missing_columns": missing, "type_mismatches": type_mismatches}

        else:
            result["status"] = "error"
            result["details"] = {"error": f"Unsupported contract type {contract_type}"}

    except Exception as exc:
        result["status"] = "error"
        result["details"] = {"error": str(exc)}

    return result
