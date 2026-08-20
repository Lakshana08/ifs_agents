"""FastAPI entrypoint that hosts a single A2A agent for creating S/4HANA
purchase orders.

  /a2a/action -> Purchase Order Agent -> /.well-known/agent-card.json, /

so a caller (e.g. a Joule Studio A2A code-based agent registration) sees
this agent at http://<host>/a2a/action/.well-known/agent-card.json.
"""

from dotenv import load_dotenv
from fastapi import FastAPI

# Must run before any gen_ai_hub import: the AI Core SDK reads
# AICORE_CLIENT_ID/CLIENT_SECRET/AUTH_URL/BASE_URL/RESOURCE_GROUP directly
# from os.environ (see app/services/ai_core.py) rather than through
# app.core.config.Settings, so .env values need to land in the real process
# environment for local development.
load_dotenv()

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import add_a2a_routes_to_fastapi, create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.utils.constants import DEFAULT_RPC_URL

from app.a2a_agents.action_agent import ActionAgentExecutor, build_action_agent_card
from app.core.config import get_settings

_AGENTS = {
    "action": (build_action_agent_card, ActionAgentExecutor),
}


def _build_agent_app(path_segment: str, build_card, executor_cls) -> FastAPI:
    settings = get_settings()
    # Trailing slash matters: create_jsonrpc_routes registers the RPC endpoint
    # at DEFAULT_RPC_URL ("/") relative to this mounted sub-app, so the real
    # external path is ".../a2a/<segment>/" - advertising it without the
    # trailing slash makes strict A2A clients choke on the 307 redirect.
    base_url = f"{settings.app_public_url}/a2a/{path_segment}/"
    card = build_card(base_url=base_url)
    handler = DefaultRequestHandler(
        agent_executor=executor_cls(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    agent_app = FastAPI(title=card.name)
    add_a2a_routes_to_fastapi(
        agent_app,
        agent_card_routes=create_agent_card_routes(card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url=DEFAULT_RPC_URL),
    )
    return agent_app


def create_app() -> FastAPI:
    app = FastAPI(title="Purchase Order Agent")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    for path_segment, (build_card, executor_cls) in _AGENTS.items():
        app.mount(f"/a2a/{path_segment}", _build_agent_app(path_segment, build_card, executor_cls))

    return app


app = create_app()
