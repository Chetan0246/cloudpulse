"""
API Lambda entry point.

Architecture Decision (ADR-006):
  We use API Gateway (HTTP API) → Lambda proxy → Mangum → FastAPI.

  Mangum translates the Lambda proxy event into an ASGI-compatible
  request, passes it to FastAPI, and translates the response back into
  the Lambda proxy response format.

  The FastAPI app (backend/app/main.py) has zero Lambda-specific code.
  It can be run locally with `uvicorn app.main:app --reload` and tested
  with the standard FastAPI TestClient — no Lambda runtime needed.

  Mangum version is pinned in lambda/api/requirements.txt to match the
  FastAPI version in backend/requirements.txt.

Cold start note:
  Lambda cold starts with FastAPI + Mangum typically take 1-2 seconds.
  For an academic demo this is acceptable. If sub-500ms cold starts were
  required, we would use a plain Lambda handler or a lighter framework.
"""
import sys
import os

# Lambda packages backend/ as a layer; add it to the path.
# In production this is handled by the SAM build process.
sys.path.insert(0, "/opt/python")  # Lambda layer path

from mangum import Mangum  # type: ignore[import-untyped]

from app.main import app  # FastAPI application from backend/

# Mangum wraps FastAPI's ASGI interface for Lambda
# lifespan="off" because we handle startup via FastAPI's lifespan context
handler = Mangum(app, lifespan="off")
