import json

from pydantic import ValidationError


def response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body, default=str),
    }


def parse_json(event: dict, model):
    try:
        return model.model_validate(json.loads(event.get("body") or "{}"))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ValueError(str(exc)) from exc
