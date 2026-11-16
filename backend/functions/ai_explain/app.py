import json

from backend.common.services.claude_service import explain


def lambda_handler(event, context):
    payload = json.loads(event.get("body") or "{}")
    question, facts = payload.get("question", ""), payload.get("facts", {})
    if not isinstance(question, str) or not question.strip() or not isinstance(facts, dict):
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "question and facts are required",
                    }
                }
            ),
        }
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(explain(question, facts)),
    }
