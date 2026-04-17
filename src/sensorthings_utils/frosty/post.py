"""Execute POST requests with local or external FROST servers."""

# standard
import json
from typing import Any, Mapping

# external
import requests

# internal
from .errors import FrostRequestError


def _general_post(
    url: str,
    payload: Mapping[str, Any] | str,
    *,
    auth_headers: str | None = None,
    content_type: str = "application/json",
) -> requests.Response:
    """
    Execute a POST request against a FROST endpoint.

    Accepts structured payloads (mapping/list) and serializes them to JSON bytes.
    String payloads are UTF-8 encoded directly.
    """
    request_data = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": content_type}
    if auth_headers:
        headers["Authorization"] = f"Basic {auth_headers}"

    try:
        response = requests.post(url=url, data=request_data, headers=headers)
        response.raise_for_status()
        return response
    except Exception as exc:
        raise FrostRequestError(exc, url)

