"""Vercel Serverless Function for MRP++ API.

Vercel hands Python functions a WSGI-style ``handler(event, context)`` contract,
but the application is ASGI (FastAPI). The previous implementation wrapped the
ASGI app in ``WsgiToAsgiAdapter`` (the wrong direction) and drove it through a
synchronous ``TestClient``, so every request failed. Here the event is replayed
into the ASGI app directly via ``httpx.ASGITransport``.
"""

import asyncio
import base64
import os
import sys

# Make the project root importable from api/index.py.
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Vercel's filesystem is read-only apart from /tmp, so keep the SQLite file there
# unless the platform provides a real DATABASE_URL.
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:////tmp/mrp.db"

import httpx  # noqa: E402
from database import init_db  # noqa: E402
from main import app  # noqa: E402

init_db()

_transport = httpx.ASGITransport(app=app)


async def _call_asgi(method, path, query, headers, body):
    async with httpx.AsyncClient(transport=_transport, base_url="http://internal") as client:
        return await client.request(
            method, path, params=query, headers=headers, content=body
        )


def handler(event, context=None):
    """Handle a Vercel serverless request."""
    method = (event.get("httpMethod") or event.get("method") or "GET").upper()
    path = event.get("path") or event.get("rawPath") or "/"

    query = event.get("queryStringParameters") or event.get("query") or {}
    if isinstance(query, str):
        query = dict(pair.split("=", 1) for pair in query.split("&") if "=" in pair)

    # Vercel normalises header casing inconsistently; HTTP/1.1 header names are
    # case-insensitive but Starlette expects lowercase.
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    headers.pop("host", None)
    headers.pop("content-length", None)

    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body)
    elif isinstance(body, str):
        body = body.encode()

    response = asyncio.run(_call_asgi(method, path, query, headers, body))

    return {
        "statusCode": response.status_code,
        "headers": dict(response.headers),
        "body": response.text,
    }
