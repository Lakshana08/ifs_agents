from langchain_core.tools import tool

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentSkill

from app.a2a_agents.common import build_agent_card, build_response_message, get_structured_input
from app.core_capabilities.action import perform_purchase_order_action
from app.services.ai_core import run_agent
from app.services.s4_client import S4ClientError

SKILL = AgentSkill(
    id="create_purchase_order",
    name="Create Purchase Order",
    description=(
        "Creates a Purchase Order in S/4HANA (T-code ME21N, API_PURCHASEORDER_PROCESS_SRV). "
        "Requires action 'create_purchase_order' and a payload with header fields "
        "PurchaseOrderType, Supplier, CompanyCode, PurchasingOrganization, PurchasingGroup, "
        "DocumentCurrency, plus a to_PurchaseOrderItem list where each item needs "
        "PurchaseOrderItem, Material, Plant, OrderQuantity, PurchaseOrderQuantityUnit, "
        "NetPriceAmount (StorageLocation, NetPriceQuantity, DocumentCurrency optional per item). "
        "Accepts either structured JSON (action, payload) or a plain free-text instruction."
    ),
    tags=["s4hana", "purchase-order", "action", "me21n", "procurement"],
    examples=[
        (
            "Create a purchase order for supplier 10200001 at company code 1010, "
            "purchasing org 1010, group 100, currency USD, for 100 PC of material SP002 "
            "at plant 1010 storage location V01, net price 10.00"
        ),
    ],
    input_modes=["application/json", "text/plain"],
    output_modes=["application/json", "text/plain"],
)


@tool
def create_purchase_order(
    purchase_order_type: str,
    supplier: str,
    company_code: str,
    purchasing_organization: str,
    purchasing_group: str,
    document_currency: str,
    items: list[dict],
) -> dict:
    """Create a Purchase Order header plus items in one call. items is a list of dicts,
    each requiring purchase_order_item, material, plant, order_quantity,
    purchase_order_quantity_unit, net_price_amount (storage_location, net_price_quantity,
    document_currency optional per item)."""
    item_field_map = {
        "purchase_order_item": "PurchaseOrderItem",
        "material": "Material",
        "plant": "Plant",
        "storage_location": "StorageLocation",
        "order_quantity": "OrderQuantity",
        "purchase_order_quantity_unit": "PurchaseOrderQuantityUnit",
        "net_price_amount": "NetPriceAmount",
        "net_price_quantity": "NetPriceQuantity",
        "document_currency": "DocumentCurrency",
    }
    mapped_items = [
        {sap_field: item[key] for key, sap_field in item_field_map.items() if item.get(key) is not None}
        for item in items
    ]
    payload = {
        "PurchaseOrderType": purchase_order_type,
        "Supplier": supplier,
        "CompanyCode": company_code,
        "PurchasingOrganization": purchasing_organization,
        "PurchasingGroup": purchasing_group,
        "DocumentCurrency": document_currency,
        "to_PurchaseOrderItem": mapped_items,
    }
    return perform_purchase_order_action(action="create_purchase_order", payload=payload)


_TOOLS = [create_purchase_order]

_AGENT_SYSTEM_PROMPT = """You create Purchase Orders in S/4HANA using the tool available. Only \
call the tool if the user's instruction clearly states all the required values (purchase order \
type, supplier, company code, purchasing organization, purchasing group, document currency, and \
at least one item with material, plant, order quantity, quantity unit, and net price amount) - \
never guess or invent values. If anything required is missing or ambiguous, ask the user to \
clarify instead of calling the tool. Keep answers short and factual (1-2 sentences)."""


def build_action_agent_card(base_url: str):
    return build_agent_card(
        name="Purchase Order Agent",
        description="Creates Purchase Orders in S/4HANA via API_PURCHASEORDER_PROCESS_SRV.",
        skill=SKILL,
        base_url=base_url,
    )


class ActionAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        args = get_structured_input(context)

        if args is not None:
            action = args.get("action", "create_purchase_order")
            payload = args.get("payload")

            try:
                result = perform_purchase_order_action(action=action, payload=payload)
            except S4ClientError as exc:
                await event_queue.enqueue_event(
                    build_response_message(context, f"Action failed against S/4HANA: {exc}", {"error": "s4_error"})
                )
                return
            except ValueError as exc:
                await event_queue.enqueue_event(
                    build_response_message(context, str(exc), {"error": "invalid_action"})
                )
                return

            summary = f"Action '{action}' completed. Purchase order: {result.get('purchase_order')}."
            await event_queue.enqueue_event(build_response_message(context, summary, result))
            return

        # Free text - let the AI Core tool-calling agent decide what to call.
        text = context.get_user_input()
        agent_result = await run_agent(_AGENT_SYSTEM_PROMPT, _TOOLS, text)
        if agent_result is None:
            await event_queue.enqueue_event(
                build_response_message(
                    context,
                    "I couldn't process that request right now (AI Core unavailable).",
                    {"error": "ai_core_unavailable"},
                )
            )
            return

        answer, tool_outputs = agent_result
        data = {"tool_results": tool_outputs} if tool_outputs else None
        await event_queue.enqueue_event(build_response_message(context, answer, data))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None
