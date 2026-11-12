"""Minimal Cisco FMC REST API client."""

import time

import requests
import urllib3

PAGE_LIMIT = 1000
RATE_LIMIT_WAIT = 10
MAX_ATTEMPTS = 10


class SetupError(Exception):
    """Error that stops the current menu option and is shown to the user."""


def error_text(response):
    """Error description returned by FMC, or the beginning of the raw response."""
    try:
        messages = response.json()["error"]["messages"]
        return "; ".join(m.get("description", "") for m in messages)
    except (ValueError, KeyError, TypeError):
        return response.text[:500]


def report(response, ok_message):
    """Prints the result of a POST request. Returns True on success."""
    if response.status_code in (200, 201, 202):
        print(ok_message)
        return True
    print(f"Error occurred in POST (HTTP {response.status_code}) --> {error_text(response)}")
    return False


class FMCClient:
    """Session to the FMC configuration API of the domain the user logs in to."""

    def __init__(self, host, username, password, verify=False, timeout=120):
        self.host = host.removeprefix("https://").removeprefix("http://").rstrip("/")
        self.server = "https://" + self.host
        self.username = username
        self.password = password
        self.timeout = timeout
        self.domain_uuid = None
        self.session = requests.Session()
        # FMC uses a self-signed certificate by default. Pass a CA bundle path to verify it.
        self.session.verify = verify
        if verify is False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.headers["Content-Type"] = "application/json"
        self.authenticate()

    def authenticate(self):
        response = self.session.post(
            self.server + "/api/fmc_platform/v1/auth/generatetoken",
            auth=(self.username, self.password),
            timeout=30,
        )
        token = response.headers.get("X-auth-access-token")
        if not token:
            raise SetupError(
                f"Authentication failed (HTTP {response.status_code}). "
                "Check FMC address, username and password."
            )
        self.session.headers["X-auth-access-token"] = token
        self.domain_uuid = response.headers.get("DOMAIN_UUID")

    def request(self, method, path, **kwargs):
        """Request to /api/fmc_config/v1/domain/<domain>/<path>."""
        url = f"{self.server}/api/fmc_config/v1/domain/{self.domain_uuid}/{path}"
        reauthenticated = False
        for _ in range(MAX_ATTEMPTS):
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            # Token is valid for 30 minutes - generate a new one and repeat the request
            if response.status_code == 401 and not reauthenticated:
                self.authenticate()
                reauthenticated = True
                continue
            # FMC allows 120 API requests per minute
            if response.status_code == 429:
                print(f"FMC rate limit reached, waiting {RATE_LIMIT_WAIT} seconds...")
                time.sleep(RATE_LIMIT_WAIT)
                continue
            return response
        return response

    def get(self, path):
        """Single object."""
        response = self.request("GET", path)
        if response.status_code != 200:
            raise SetupError(f"GET {path} failed (HTTP {response.status_code}): {error_text(response)}")
        return response.json()

    def get_all(self, path):
        """All items of a collection (expanded), following pagination."""
        items = []
        offset = 0
        while True:
            response = self.request(
                "GET", path, params={"expanded": "true", "offset": offset, "limit": PAGE_LIMIT}
            )
            if response.status_code != 200:
                raise SetupError(
                    f"GET {path} failed (HTTP {response.status_code}): {error_text(response)}"
                )
            data = response.json()
            items.extend(data.get("items", []))
            offset += PAGE_LIMIT
            if offset >= data.get("paging", {}).get("count", 0):
                return items

    def post(self, path, payload, params=None):
        return self.request("POST", path, json=payload, params=params)

    def put(self, path, payload, params=None):
        return self.request("PUT", path, json=payload, params=params)
