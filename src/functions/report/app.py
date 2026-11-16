def lambda_handler(event, context):
    sources = event.get("sources", [])
    failures = sum(source.get("status") == "failed" for source in sources)
    status = (
        "failed"
        if not sources or failures == len(sources)
        else ("partial_failure" if failures else "success")
    )
    return {
        "status": status,
        "sources": sources,
        "failed_sources": failures,
        "rows": sum(source.get("rows", 0) for source in sources),
        "missing": sum(source.get("missing", 0) for source in sources),
    }
