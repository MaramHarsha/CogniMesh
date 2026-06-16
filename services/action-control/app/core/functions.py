"""Restricted expression evaluator, rule engine, and function runtime.

The rule engine and the Python function runtime both evaluate small, single
expressions in a deliberately restricted namespace. There is no access to the
builtins, imports, or attribute paths that would let an expression escape the
sandbox, so untrusted-but-reviewed action rules and functions can run safely in
the control plane. TypeScript functions are registered for completeness but are
not executed locally; the runtime records them as planned so a future external
function runner can pick them up.
"""

from __future__ import annotations

from typing import Any


# A minimal, side-effect-free subset of builtins exposed to expressions.
SAFE_NAMES: dict[str, Any] = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "sum": sum,
    "any": any,
    "all": all,
    "sorted": sorted,
    "True": True,
    "False": False,
    "None": None,
}


class ExpressionError(ValueError):
    """Raised when an expression is malformed or uses a disallowed construct."""


def _guard(expression: str) -> None:
    if not isinstance(expression, str) or not expression.strip():
        raise ExpressionError("Expression must be a non-empty string")
    # Block attribute escapes (e.g. ().__class__...) and dunder access entirely.
    if "__" in expression:
        raise ExpressionError("Expression must not contain '__'")
    if "import" in expression:
        raise ExpressionError("Expression must not contain 'import'")


def evaluate(expression: str, scope: dict[str, Any]) -> Any:
    """Evaluate a single restricted expression with `scope` variables in context."""
    _guard(expression)
    try:
        code = compile(expression, "<cognimesh-expression>", "eval")
    except SyntaxError as exc:  # pragma: no cover - exercised via callers
        raise ExpressionError(f"Invalid expression syntax: {exc.msg}") from exc
    namespace = {**SAFE_NAMES, **scope}
    try:
        return eval(code, {"__builtins__": {}}, namespace)  # noqa: S307 - sandboxed
    except ExpressionError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface as a controlled error
        raise ExpressionError(f"Expression failed to evaluate: {exc}") from exc


def evaluate_rules(rules: list[dict[str, Any]], params: dict[str, Any], obj: dict[str, Any]) -> list[str]:
    """Evaluate business rules. A rule passes when its expression is truthy.

    Returns the list of violation messages (empty when all rules pass). A rule
    whose expression cannot be evaluated is itself reported as a violation so a
    misconfigured action type fails closed rather than silently allowing writes.
    """
    scope = {"params": dict(params), "obj": dict(obj), **params}
    violations: list[str] = []
    for rule in rules:
        expression = rule.get("expression", "")
        message = rule.get("message") or f"Rule '{rule.get('id', expression)}' was violated"
        try:
            passed = bool(evaluate(expression, scope))
        except ExpressionError as exc:
            violations.append(f"Rule '{rule.get('id', 'rule')}' could not be evaluated: {exc}")
            continue
        if not passed:
            violations.append(message)
    return violations


def run_function(runtime: str, source: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a registered function.

    Python functions evaluate `source` as a single restricted expression with
    `args` (the argument dict) and each argument name available in scope.
    TypeScript functions are not executed locally and are returned as planned.
    """
    runtime = (runtime or "").lower()
    if runtime == "python":
        scope = {"args": dict(arguments), **arguments}
        result = evaluate(source, scope)
        return {"runtime": "python", "executed": True, "result": result, "error": None}
    if runtime == "typescript":
        return {
            "runtime": "typescript",
            "executed": False,
            "result": None,
            "error": None,
            "note": "TypeScript function registered; local execution is planned via an external runner.",
        }
    raise ExpressionError(f"Unsupported function runtime '{runtime}'")
