"""Vercel Serverless Function for MRP++ API."""

import os
import sys

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Initialize database
from database import init_db
init_db()

# Import the FastAPI app
from main import app

# Vercel ASGI handler
def handler(event, context):
    """Handle Vercel serverless request."""
    from asgiref.wsgi import WsgiToAsgiAdapter
    from starlette.testclient import TestClient
    
    # Create ASGI app
    asgi_app = WsgiToAsgiAdapter(app)
    client = TestClient(asgi_app)
    
    # Extract request details
    method = event.get('method', 'GET')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    body = event.get('body', '')
    
    # Make request
    response = client.request(
        method=method,
        url=path,
        headers=headers,
        content=body.encode() if body else None,
        allow_redirects=False
    )
    
    return {
        'statusCode': response.status_code,
        'headers': {k: v for k, v in response.headers.items()},
        'body': response.text
    }
