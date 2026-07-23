import os


def build_auth_headers() -> dict:
    headers = {}
    bearer = os.environ.get("API_AUTH_BEARER", "")
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    for key, value in os.environ.items():
        if key.startswith("API_HEADER_") and value:
            header_name = key.removeprefix("API_HEADER_").replace("_", "-")
            headers[header_name] = value
    return headers
