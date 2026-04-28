import hmac
from typing import Mapping, Optional


INTERNAL_REQUEST_HEADER = "x-websoft9-internal-request"
INTERNAL_REQUEST_SECRET_HEADER = "x-websoft9-internal-secret"


def has_valid_internal_gateway_auth(headers: Mapping[str, str], expected_secret: Optional[str]) -> bool:
    if not expected_secret:
        return False

    internal_marker = headers.get(INTERNAL_REQUEST_HEADER)
    internal_secret = headers.get(INTERNAL_REQUEST_SECRET_HEADER)
    if internal_marker != "1" or not internal_secret:
        return False

    return hmac.compare_digest(str(internal_secret), str(expected_secret))