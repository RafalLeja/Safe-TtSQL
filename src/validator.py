def validate_sql_query(query: str) -> dict:
    if not query.lstrip().upper().startswith("SELECT"):
        return {"error": "Only SELECT queries are allowed."}

    if ";" in query.rstrip().rstrip(";"):
        return {"error": "Multiple statements are not allowed."}

    return None
