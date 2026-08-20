"""Action capability: create a Purchase Order in S/4HANA
(T-code ME21N, API_PURCHASEORDER_PROCESS_SRV).

POST A_PurchaseOrder with a nested to_PurchaseOrderItem collection - a deep
insert in one call is SAP's own documented pattern for this API, so the
header and all items are created together, no separate item POSTs.
"""

from app.services.s4_client import get_s4_client

_PURCHASE_ORDER_PATH = "/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder"

_HEADER_REQUIRED = [
    "PurchaseOrderType",
    "Supplier",
    "CompanyCode",
    "PurchasingOrganization",
    "PurchasingGroup",
    "DocumentCurrency",
]

# Header fields callers are allowed to pass through beyond the required set
# above (e.g. free text, incoterms) - anything else in payload is ignored
# rather than rejected, since the entity supports many optional fields.
_HEADER_OPTIONAL = [
    "PurchaseOrderSubtype",
    "PaymentTerms",
    "IncotermsClassification",
    "IncotermsTransferLocation",
    "PurchasingProcessingStatus",
]

_ITEM_REQUIRED = [
    "PurchaseOrderItem",
    "Material",
    "Plant",
    "OrderQuantity",
    "PurchaseOrderQuantityUnit",
    "NetPriceAmount",
]

_ITEM_OPTIONAL = [
    "StorageLocation",
    "NetPriceQuantity",
    "DocumentCurrency",
    "PurchaseOrderItemText",
    "MaterialGroup",
]

# This Gateway's OData v2 JSON serializes Edm.Decimal/Edm.Quantity fields as
# strings (same behavior confirmed for API_PRODUCT_SRV's Edm.Decimal fields),
# and rejects a bare JSON number with CX_SXML_PARSE_ERROR ("Failed to read
# property ... at offset ...") - so these must be stringified before sending.
_DECIMAL_ITEM_FIELDS = {"OrderQuantity", "NetPriceAmount", "NetPriceQuantity"}


def _stringify(value):
    return str(value) if isinstance(value, (int, float)) else value


def perform_purchase_order_action(action: str, payload: dict | None = None) -> dict:
    """Create a Purchase Order. action must be 'create_purchase_order'; payload
    carries the header fields plus to_PurchaseOrderItem (list of item dicts).
    """
    payload = payload or {}

    if action == "create_purchase_order":
        missing_header = [f for f in _HEADER_REQUIRED if not payload.get(f)]
        if missing_header:
            raise ValueError(f"create_purchase_order requires header field(s): {', '.join(missing_header)}")

        items = payload.get("to_PurchaseOrderItem")
        if not items or not isinstance(items, list):
            raise ValueError("create_purchase_order requires a non-empty to_PurchaseOrderItem list")

        body = {field: payload[field] for field in _HEADER_REQUIRED}
        body.update({field: payload[field] for field in _HEADER_OPTIONAL if payload.get(field) is not None})

        item_bodies = []
        for idx, item in enumerate(items):
            missing_item = [f for f in _ITEM_REQUIRED if not item.get(f)]
            if missing_item:
                raise ValueError(f"to_PurchaseOrderItem[{idx}] requires field(s): {', '.join(missing_item)}")
            item_body = {field: _stringify(item[field]) for field in _ITEM_REQUIRED}
            item_body.update(
                {
                    field: _stringify(item[field]) if field in _DECIMAL_ITEM_FIELDS else item[field]
                    for field in _ITEM_OPTIONAL
                    if item.get(field) is not None
                }
            )
            item_bodies.append(item_body)
        body["to_PurchaseOrderItem"] = item_bodies

        client = get_s4_client()
        result = client.post(_PURCHASE_ORDER_PATH, json_body=body)
        entity = result.get("d", result) if isinstance(result, dict) else {}
        return {
            "status": "ok",
            "action": action,
            "purchase_order": entity.get("PurchaseOrder"),
            "response": result,
        }

    raise ValueError(f"Unknown action '{action}', expected 'create_purchase_order'")
