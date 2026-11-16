from src.common.storage import report

def lambda_handler(event, context):
    return {"status": "complete", "summary": report({"sources": event.get("sources", []), "rows": event.get("rows", 0), "missing": event.get("missing", 0)})}

