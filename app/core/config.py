from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SAP Destination service - resolves the S/4HANA system this agent calls.
    # Used only when s4_base_url below is empty (i.e. the real BTP deployment path).
    s4_destination_name: str = "S4HANA_PURCHASEORDER_API"

    # Direct-connect mode: when set, S4Client talks to this host directly
    # instead of resolving a BTP Destination - useful for developing/testing
    # against a directly reachable S/4 system (e.g. over VPN) before the
    # Destination/Connectivity services are provisioned. Leave empty to use
    # the full BTP Destination path in Cloud Foundry.
    s4_base_url: str = ""
    s4_username: str = ""
    s4_password: str = ""

    # sap-client query parameter, required by some Gateway systems (e.g.
    # ?sap-client=100) on every OData call. Leave empty if the destination
    # already pins the client itself.
    s4_sap_client: str = ""

    # Public base URL this app is reachable at once deployed - used to build
    # the A2A agent's AgentCard.supported_interfaces[].url.
    app_public_url: str = "http://localhost:8000"

    # SAP AI Core - direct Foundation Model access (gen_ai_hub.proxy.langchain),
    # used by the agent to (a) parse free-text task input into parameters and
    # (b) phrase natural-language response summaries. When False, the agent
    # only accepts structured JSON input and uses its own template summaries.
    # NOTE: credentials themselves (AICORE_CLIENT_ID/CLIENT_SECRET/AUTH_URL/
    # BASE_URL/RESOURCE_GROUP) are read directly from the process environment
    # by the gen_ai_hub SDK, not through this Settings class - see main.py's
    # load_dotenv() call.
    ai_core_enabled: bool = False
    ai_core_model_name: str = "gpt-4o-mini"

    # If set, identifies the exact AI Core deployment to call directly
    # (preferred - skips the model_name catalog lookup). Falls back to
    # ai_core_model_name above when empty.
    llm_deployment_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
