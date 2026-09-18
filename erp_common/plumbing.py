"""Generic ERPNext request plumbing shared across the fabrication and
write-back scripts - the insert-then-submit sequence and the ad hoc
response-unwrapping every script was repeating inline.
"""


def unwrap(result):
    """ERPClient responses inconsistently nest the real payload under
    'data' (REST resource endpoints) or 'message' (whitelisted method
    calls). Unwrap once, centrally, instead of each caller repeating
    `result.get("data", result) if isinstance(result, dict) else result`.
    """
    if isinstance(result, dict):
        if "data" in result:
            return result["data"]
        if "message" in result:
            return result["message"]
    return result


def create_and_submit(client, doctype, fields):
    """Insert a new doc and submit it in one step. Returns the created name.

    Covers the pattern every fabrication script was hand-rolling: insert,
    unwrap the response, pull `name`, submit.
    """
    result = client.insert_doc(doctype, fields)
    data = unwrap(result)
    name = data["name"]
    client.submit_doc(doctype, name)
    return name
