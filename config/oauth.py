import base64
import hashlib
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

AUTH_URL = "https://openrouter.ai/auth"
# Token exchange lives under the API base; keep it in step with base_url.
KEYS_PATH = "/auth/keys"

# How long we'll wait for the user to finish authorizing in the browser.
CALLBACK_TIMEOUT_SECONDS = 300


class OAuthError(Exception):
    """Raised when the OAuth flow can't be completed."""


def _generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for the S256 method."""
    # 32 random bytes -> 43-char base64url string, within the RFC 7636
    # 43..128 length window.
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    """Single-shot handler that captures the `code` from the redirect."""

    # Set by the server factory below.
    result: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        code = params.get("code", [None])[0]

        if code:
            type(self).result["code"] = code
            body = "<h2>relay is now logged in.</h2><p>You can close this tab.</p>"
        else:
            type(self).result["error"] = params.get("error", ["unknown error"])[0]
            body = "<h2>Login failed.</h2><p>You can close this tab and try again.</p>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_args) -> None:
        # Silence the default stderr request logging; it just clutters the CLI.
        pass


def _wait_for_code(server: HTTPServer, result: dict[str, str]) -> str:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Poll rather than block forever so a user who never finishes in the
        # browser eventually gets a clear timeout instead of a hung CLI.
        deadline = threading.Event()
        waited = 0.0
        while not (result.get("code") or result.get("error")):
            if deadline.wait(0.25):
                break
            waited += 0.25
            if waited >= CALLBACK_TIMEOUT_SECONDS:
                raise OAuthError("Timed out waiting for browser authorization.")
    finally:
        server.shutdown()
        thread.join(timeout=1)

    if result.get("error"):
        raise OAuthError(f"Authorization was denied: {result['error']}")
    return result["code"]


def _exchange_code(base_url: str, code: str, verifier: str) -> str:
    keys_url = base_url.rstrip("/") + KEYS_PATH
    try:
        resp = httpx.post(
            keys_url,
            json={
                "code": code,
                "code_verifier": verifier,
                "code_challenge_method": "S256",
            },
            timeout=30,
        )
        resp.raise_for_status()
        key = resp.json().get("key")
    except httpx.HTTPError as e:
        raise OAuthError(f"Failed to exchange code for a key: {e}") from e

    if not key:
        raise OAuthError("OpenRouter did not return an API key.")
    return key


def login_with_oauth(base_url: str, open_browser=webbrowser.open) -> str:
    verifier, challenge = _generate_pkce_pair()

    # Port 0 -> the OS hands us a free ephemeral port. OpenRouter accepts any
    # localhost callback, so nothing needs pre-registering.
    handler = type("_Handler", (_CallbackHandler,), {"result": {}})
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    callback_url = f"http://localhost:{port}"

    params = urllib.parse.urlencode(
        {
            "callback_url": callback_url,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    auth_url = f"{AUTH_URL}?{params}"

    opened = False
    try:
        opened = open_browser(auth_url)
    except webbrowser.Error:
        opened = False

    if not opened:
        # Headless / no default browser: let the user open it themselves.
        print("Open this URL in your browser to authorize relay:")
        print(f"  {auth_url}")

    code = _wait_for_code(server, handler.result)
    return _exchange_code(base_url, code, verifier)
