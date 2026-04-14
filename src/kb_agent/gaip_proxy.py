"""
GAIP Proxy Service
==================
A standalone, reusable HTTP proxy that translates standard OpenAI-compatible
API calls into HSBC Group AI Platform (GAIP) authenticated requests.

Standalone usage:
    python -m kb_agent.gaip_proxy --endpoint https://gaip-api-uat.hsbc-... \\
                                   --user-id UCXXXXXXX \\
                                   --am-token <token> \\
                                   --port 7999

Embedded usage (kb-agent/kb-cli):
    from kb_agent.gaip_proxy import GaipProxyService, maybe_start_gaip_proxy
    proxy = maybe_start_gaip_proxy(settings)   # returns None if disabled
    ...
    if proxy:
        proxy.stop()
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Core proxy class ────────────────────────────────────────────────────────

class GaipProxyService:
    """
    Wraps a local FastAPI/uvicorn server that proxies OpenAI-compatible
    requests to the HSBC Group AI Platform (GAIP) API.

    Thread-safe: start() spins up an asyncio event loop in a daemon thread.
    stop()  signals uvicorn to shut down gracefully.

    Token hot-refresh: on every request the proxy re-reads the AMToken from
    kb_agent.config.settings so that a 30-min token renewal in the TUI takes
    effect immediately without a restart.
    """

    def __init__(
        self,
        endpoint: str,
        user_id: str,
        am_token: str,
        port: int = 7999,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.user_id = user_id
        self.am_token = am_token          # fallback if config unavailable
        self.port = port

        self._server: Optional[object] = None   # uvicorn.Server
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the proxy in a background daemon thread. Blocks until ready (~1 s)."""
        if self._thread and self._thread.is_alive():
            logger.warning("GAIP proxy already running on port %s", self.port)
            return

        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="gaip-proxy",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(timeout=8.0):
            logger.error("GAIP proxy failed to start within 8 s")
        else:
            logger.info("GAIP proxy listening on http://127.0.0.1:%s/v1", self.port)

    def stop(self) -> None:
        """Signal uvicorn to exit; the daemon thread will die on its own."""
        if self._server:
            self._server.should_exit = True   # type: ignore[attr-defined]
        logger.info("GAIP proxy stop requested")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── internal ──────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Entry point for the background thread – owns its own event loop."""
        try:
            import uvicorn
        except ImportError:
            logger.error(
                "uvicorn not installed. Run: pip install 'fastapi[standard]' httpx"
            )
            self._ready.set()
            return

        app = self._build_app()
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # Signal ready shortly after server starts
        self._loop.call_later(0.8, self._ready.set)

        try:
            self._loop.run_until_complete(self._server.serve())
        finally:
            self._loop.close()

    def _get_am_token(self) -> str:
        """Hot-read token from live config so 30-min renewals take effect immediately."""
        try:
            from kb_agent import config as cfg  # lazy – may not be available in standalone
            if cfg.settings and cfg.settings.gaip_am_token:
                return cfg.settings.gaip_am_token.get_secret_value()
        except Exception:
            pass
        return self.am_token

    def _gaip_headers(self) -> dict:
        return {
            "AMToken": self._get_am_token(),
            "Content-Type": "application/json",
            "Token_Type": "SESSION_TOKEN",
            "x-correlation-id": str(uuid.uuid4()),
            "x-usersession-id": str(uuid.uuid4()),
        }

    def _build_app(self):
        """Build and return the FastAPI application."""
        try:
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse, StreamingResponse
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependencies. Run: pip install 'fastapi[standard]' httpx"
            ) from exc

        app = FastAPI(title="GAIP Proxy", version="1.0.0", docs_url=None, redoc_url=None)
        proxy = self   # closure reference

        # ── /v1/chat/completions ─────────────────────────────────────────

        @app.post("/v1/chat/completions")
        async def chat_completions(request: Request):
            body: dict = await request.json()

            # Cap max_tokens at 64 k (GAIP platform limit)
            if body.get("max_tokens", 0) > 65536:
                body["max_tokens"] = 65536

            # Inject GAIP required "user" field
            body["user"] = proxy.user_id

            headers = proxy._gaip_headers()
            target_url = f"{proxy.endpoint}/chat/completions"
            is_stream = body.get("stream", False)

            if is_stream:
                async def _stream():
                    async with httpx.AsyncClient(timeout=120.0, verify=True) as client:
                        async with client.stream(
                            "POST",
                            target_url,
                            json=body,
                            headers=headers,
                        ) as resp:
                            async for chunk in resp.aiter_bytes():
                                yield chunk

                return StreamingResponse(_stream(), media_type="text/event-stream")

            else:
                async with httpx.AsyncClient(timeout=120.0, verify=True) as client:
                    resp = await client.post(target_url, json=body, headers=headers)
                    return JSONResponse(content=resp.json(), status_code=resp.status_code)

        # ── /v1/embeddings ───────────────────────────────────────────────

        @app.post("/v1/embeddings")
        async def embeddings(request: Request):
            body: dict = await request.json()
            headers = proxy._gaip_headers()

            async with httpx.AsyncClient(timeout=60.0, verify=True) as client:
                resp = await client.post(
                    f"{proxy.endpoint}/embeddings",
                    json=body,
                    headers=headers,
                )
                return JSONResponse(content=resp.json(), status_code=resp.status_code)

        # ── /v1/models  (stub so OpenAI clients don't choke) ────────────

        @app.get("/v1/models")
        async def list_models():
            return {
                "object": "list",
                "data": [
                    {
                        "id": "GPT-4o",
                        "object": "model",
                        "created": 0,
                        "owned_by": "gaip",
                    }
                ],
            }

        # ── /health ──────────────────────────────────────────────────────

        @app.get("/health")
        async def health():
            return {"status": "ok", "proxy": "gaip", "port": proxy.port}

        return app


# ─── Convenience helper used by cli.py / skill_cli.py ───────────────────────

def maybe_start_gaip_proxy(settings) -> Optional[GaipProxyService]:
    """
    Check settings and start the GAIP proxy if enabled.
    Returns the running GaipProxyService or None if disabled / mis-configured.
    """
    if not getattr(settings, "gaip_proxy_enabled", False):
        return None

    endpoint = getattr(settings, "gaip_api_endpoint", None)
    user_id = getattr(settings, "gaip_user_id", None)
    am_token_field = getattr(settings, "gaip_am_token", None)
    port = getattr(settings, "gaip_proxy_port", None) or 7999

    if not endpoint or not user_id or not am_token_field:
        logger.warning(
            "GAIP proxy enabled but endpoint/user_id/am_token not configured – skipping."
        )
        return None

    am_token = (
        am_token_field.get_secret_value()
        if hasattr(am_token_field, "get_secret_value")
        else str(am_token_field)
    )

    proxy = GaipProxyService(
        endpoint=endpoint,
        user_id=user_id,
        am_token=am_token,
        port=port,
    )
    proxy.start()
    return proxy


# ─── Standalone CLI entrypoint ───────────────────────────────────────────────

def _standalone_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="GAIP Proxy – OpenAI-compatible proxy for HSBC Group AI Platform"
    )
    parser.add_argument("--endpoint", required=True, help="GAIP API base URL")
    parser.add_argument("--user-id", required=True, help="Your UCXXXXXXX user ID")
    parser.add_argument("--am-token", required=True, help="AMToken (Internal Staff JWT)")
    parser.add_argument("--port", type=int, default=7999, help="Local port (default: 7999)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    proxy = GaipProxyService(
        endpoint=args.endpoint,
        user_id=args.user_id,
        am_token=args.am_token,
        port=args.port,
    )
    proxy.start()

    print(f"\n✅  GAIP Proxy running → http://127.0.0.1:{args.port}/v1")
    print("   Press Ctrl-C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        proxy.stop()
        print("\nProxy stopped.")


if __name__ == "__main__":
    _standalone_main()
