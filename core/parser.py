import json
import re


def parse_json(raw: str) -> dict:
    """
    Cleans and parses a JSON string that may contain markdown fences or extra text.

    Args:
        raw: Raw string output from the LLM.

    Returns:
        Parsed dictionary, or an empty dict on failure.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    # Extract the first JSON object found
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        json_str = match.group(0)
    else:
        json_str = cleaned

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[parser] JSON decode error: {e}")
        return {}
