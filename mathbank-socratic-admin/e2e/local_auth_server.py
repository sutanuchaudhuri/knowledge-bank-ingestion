"""Test-only loopback API using real local session handlers; no catalog fixtures."""
import os
import socket

import bcrypt
import uvicorn
from fastapi import APIRouter, FastAPI

os.environ.update({
    "SOCRATIC_AUTH_MODE": "local",
    "SOCRATIC_LOCAL_USERNAME": "browser-author",
    "SOCRATIC_LOCAL_PASSWORD_HASH": bcrypt.hashpw(
        b"synthetic-browser-test-password", bcrypt.gensalt(rounds=4),
    ).decode(),
    "SOCRATIC_LOCAL_CAPABILITIES": '["author"]',
    "SOCRATIC_CSRF_SECRET": "synthetic-browser-csrf-secret-for-offline-tests",
    "SOCRATIC_ALLOWED_ORIGINS": '["http://127.0.0.1:5188"]',
    "SOCRATIC_COOKIE_SECURE": "false",
})

from mathbank_rest.routers.socratic import router

original_connect = socket.socket.connect


def loopback_connect(sock, address):
    if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
        raise RuntimeError("Offline browser server cannot connect outside loopback.")
    return original_connect(sock, address)


socket.socket.connect = loopback_connect
app = FastAPI(title="Offline local staff auth test server")
app.include_router(APIRouter(routes=[route for route in router.routes if route.path.endswith("/session")]))
uvicorn.run(app, host="127.0.0.1", port=8018, proxy_headers=False, access_log=False)
