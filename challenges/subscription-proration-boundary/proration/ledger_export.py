"""CSV lines of id,cents. Does not compute a credit."""
def export_rows(rows: list[tuple[str, int]]) -> str:
    return "\n".join(f"{a},{b}" for a, b in rows)
