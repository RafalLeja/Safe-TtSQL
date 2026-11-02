def validate_sql_query(query: str) -> dict[str, str]:
    if not query.lstrip().upper().startswith("SELECT"):
        return {"error": "Only SELECT queries are allowed."}

    if ";" in query.rstrip().rstrip(";"):
        return {"error": "Multiple statements are not allowed."}

    return {"success": "True"}
