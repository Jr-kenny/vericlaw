def gather_web_evidence(query: str, search) -> list:
    """search: callable(query)->list[{"url","snippet"}]. Never raises."""
    try:
        return list(search(query))
    except Exception:
        return []
