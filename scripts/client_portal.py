"""Client Portal API client.

Thin wrapper around https://api-clientportal.technijian.com.

- Auth: POST /api/auth/token with {userName,password} -> bearer token
- Token cached in tracking/kb/cache/token.json (gitignored)
- SP exec: POST /api/modules/{module}/stored-procedures/client-portal/dbo/{sp}/execute
    body = {"Parameters": {...}}
- Catalog guide: GET /api/catalog/guide/{databaseAlias}/{schema}/{name}
    -> returns parameter + result-set schema for an SP

Usage:
    from client_portal import ClientPortal
    cp = ClientPortal()
    rows = cp.exec_sp("projectproposal", "GET_PROPOSALS_LIST", {})
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request, parse, error

REPO = Path(__file__).resolve().parent.parent
SECRETS_FILE = REPO / "scripts" / "secrets.json"
CACHE_DIR = REPO / "tracking" / "kb" / "cache"
TOKEN_FILE = CACHE_DIR / "token.json"


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str, url: str):
        super().__init__(f"HTTP {status} on {url}: {body[:400]}")
        self.status = status
        self.body = body
        self.url = url


@dataclass
class Token:
    access_token: str
    expires_at: float  # epoch seconds

    def is_valid(self) -> bool:
        return time.time() < (self.expires_at - 60)


class ClientPortal:
    def __init__(self, secrets_path: Path = SECRETS_FILE):
        self.secrets_path = secrets_path
        cfg = json.loads(secrets_path.read_text(encoding="utf-8"))["clientPortal"]
        self.base_url: str = cfg["baseUrl"].rstrip("/")
        self._user: str = cfg["userName"]
        self._pw: str = cfg["password"]
        self._token: Token | None = None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_cached_token()

    # ---------- token management ----------

    def _load_cached_token(self) -> None:
        if TOKEN_FILE.exists():
            try:
                d = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
                t = Token(d["accessToken"], d["expiresAt"])
                if t.is_valid():
                    self._token = t
            except Exception:
                pass

    def _save_token(self, tok: Token) -> None:
        TOKEN_FILE.write_text(
            json.dumps({"accessToken": tok.access_token, "expiresAt": tok.expires_at}),
            encoding="utf-8",
        )

    def _authenticate(self) -> Token:
        url = f"{self.base_url}/api/auth/token"
        body = json.dumps({"userName": self._user, "password": self._pw}).encode()
        req = request.Request(url, data=body, method="POST",
                              headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        expires_in = int(data.get("expiresIn", 3600))
        tok = Token(data["accessToken"], time.time() + expires_in)
        self._save_token(tok)
        return tok

    def token(self) -> str:
        if self._token is None or not self._token.is_valid():
            self._token = self._authenticate()
        return self._token.access_token

    # ---------- HTTP ----------

    def _request(self, method: str, path: str, body: dict | None = None,
                 retries: int = 2) -> Any:
        url = f"{self.base_url}{path}"
        for attempt in range(retries + 1):
            data = None if body is None else json.dumps(body).encode()
            req = request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self.token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
            try:
                with request.urlopen(req, timeout=120) as resp:
                    raw = resp.read()
                    if not raw:
                        return None
                    return json.loads(raw)
            except error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                if e.code == 401 and attempt < retries:
                    # Force re-auth
                    self._token = None
                    continue
                if e.code in (429, 502, 503, 504) and attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise ApiError(e.code, raw, url)
            except error.URLError as e:
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise ApiError(0, str(e), url)

    # ---------- high-level ----------

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def exec_sp(self, module: str, sp: str, params: dict[str, Any] | None = None) -> Any:
        path = f"/api/modules/{module}/stored-procedures/client-portal/dbo/{sp}/execute"
        return self._request("POST", path, body={"Parameters": params or {}})

    @staticmethod
    def xml_rows(result: dict, element: str = "Report") -> list[dict]:
        """Parse XML_OUT output parameter into a list of dicts.

        Many SPs whose name starts with ``stp_xml_`` return data not in
        ``resultSets`` but in ``outputParameters.XML_OUT`` as an XML string
        with a flat structure like ``<Root><Report><field>...</field></Report></Root>``.
        """
        if not isinstance(result, dict):
            return []
        op = result.get("outputParameters") or result.get("OutputParameters") or {}
        xml = op.get("XML_OUT") or op.get("xml_out")
        if not xml:
            return []
        import xml.etree.ElementTree as ET
        import html as htmllib
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []
        out: list[dict] = []
        for node in root.findall(f".//{element}"):
            row: dict = {}
            for child in node:
                row[child.tag] = htmllib.unescape((child.text or "").strip())
            out.append(row)
        return out

    def catalog_guide(self, database: str, schema: str, name: str) -> Any:
        path = f"/api/catalog/guide/{parse.quote(database)}/{parse.quote(schema)}/{parse.quote(name)}"
        return self._request("GET", path)

    def list_active_clients(self) -> Any:
        return self.get("/api/clients/active")


if __name__ == "__main__":
    # Smoke test
    cp = ClientPortal()
    tok = cp.token()
    print(f"OK token length={len(tok)}")
    h = cp.get("/api/system/health")
    print(f"health: {h}")
