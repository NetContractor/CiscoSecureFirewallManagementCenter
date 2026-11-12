import pytest

from fmc_setup import client as client_module
from fmc_setup.client import FMCClient, SetupError


class Response:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {}
        self.text = str(body)

    def json(self):
        return self._body


AUTH_OK = Response(204, headers={"X-auth-access-token": "token", "DOMAIN_UUID": "domain"})


class Session:
    """requests.Session double returning queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}
        self.verify = True

    def post(self, url, **kwargs):
        self.calls.append(("AUTH", url, kwargs))
        return self.responses.pop(0)

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def make_client(monkeypatch, responses):
    session = Session(responses)
    monkeypatch.setattr(client_module.requests, "Session", lambda: session)
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)
    return FMCClient("https://fmc.example.com/", "user", "pass"), session


def test_authentication(monkeypatch):
    fmc, session = make_client(monkeypatch, [AUTH_OK])
    assert fmc.host == "fmc.example.com"
    assert fmc.domain_uuid == "domain"
    assert session.headers["X-auth-access-token"] == "token"
    assert session.verify is False


def test_authentication_failure(monkeypatch):
    with pytest.raises(SetupError, match="Authentication failed"):
        make_client(monkeypatch, [Response(401)])


def test_get_all_follows_pagination(monkeypatch):
    monkeypatch.setattr(client_module, "PAGE_LIMIT", 2)
    pages = [
        Response(200, {"items": [{"name": "a"}, {"name": "b"}], "paging": {"count": 3}}),
        Response(200, {"items": [{"name": "c"}], "paging": {"count": 3}}),
    ]
    fmc, session = make_client(monkeypatch, [AUTH_OK] + pages)
    assert [i["name"] for i in fmc.get_all("object/hosts")] == ["a", "b", "c"]
    assert session.calls[2][2]["params"]["offset"] == 2
    assert session.calls[1][1] == "https://fmc.example.com/api/fmc_config/v1/domain/domain/object/hosts"


def test_expired_token_is_renewed(monkeypatch):
    fmc, session = make_client(monkeypatch, [AUTH_OK, Response(401), AUTH_OK, Response(201)])
    assert fmc.post("object/hosts", {}).status_code == 201
    assert [call[0] for call in session.calls] == ["AUTH", "POST", "AUTH", "POST"]


def test_rate_limit_is_retried(monkeypatch):
    fmc, _ = make_client(monkeypatch, [AUTH_OK, Response(429), Response(201)])
    assert fmc.post("object/hosts", {}).status_code == 201


def test_get_error_shows_fmc_message(monkeypatch):
    error = Response(400, {"error": {"messages": [{"description": "Invalid object"}]}})
    fmc, _ = make_client(monkeypatch, [AUTH_OK, error])
    with pytest.raises(SetupError, match="Invalid object"):
        fmc.get_all("object/hosts")
