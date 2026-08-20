# Purchase Order Agent

A single A2A agent that creates Purchase Orders in S/4HANA
(T-code ME21N, `API_PURCHASEORDER_PROCESS_SRV` / `A_PurchaseOrder`), header
plus items in one deep-insert POST.

Structurally this is the same shape as `product_supply_planning_agent`
(destination resolution, CSRF-aware OData client, A2A skill wrapper) - just
pointed at a different OData service and a create (POST) instead of an
update (PATCH).

## Run locally

```
pip install --no-deps -r requirements.txt
cp .env.example .env   # fill in S4_BASE_URL / S4_USERNAME / S4_PASSWORD / S4_SAP_CLIENT for direct-connect dev
uvicorn app.main:app --reload
```

`requirements.txt` is a full pinned lockfile (direct + transitive
dependencies), installed with `--no-deps`. This is required because
`generative-ai-hub-sdk` hard-pins `pydantic==2.10.6`, which conflicts with
`a2a-sdk`'s `pydantic>=2.11.3` requirement - normal `pip install -r
requirements.txt` dependency resolution cannot satisfy both at once. See the
comments at the top of `requirements.txt` before adding or upgrading a
dependency.

Agent discovery: `http://localhost:8000/a2a/action/.well-known/agent-card.json`
JSON-RPC endpoint: `http://localhost:8000/a2a/action/`

## Example structured-JSON call

```json
{
  "action": "create_purchase_order",
  "payload": {
    "PurchaseOrderType": "RO",
    "Supplier": "10200001",
    "CompanyCode": "1010",
    "PurchasingOrganization": "1010",
    "PurchasingGroup": "100",
    "DocumentCurrency": "USD",
    "to_PurchaseOrderItem": [
      {
        "PurchaseOrderItem": "10",
        "Material": "SP002",
        "Plant": "1010",
        "StorageLocation": "V01",
        "OrderQuantity": "100",
        "PurchaseOrderQuantityUnit": "PC",
        "NetPriceAmount": "10.00",
        "NetPriceQuantity": "1",
        "DocumentCurrency": "USD"
      }
    ]
  }
}
```

This posts to `<S4_BASE_URL>/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder`
with `sap-client=<S4_SAP_CLIENT>` appended automatically, mirroring the
sample call this agent was built from:

```
POST http://192.168.8.69:50000/sap/opu/odata/sap/api_purchaseorder_process_srv/A_PurchaseOrder?sap-client=100
```

Free-text instructions (e.g. "Create a PO for supplier 10200001 at company
code 1010 ... 100 PC of SP002 at plant 1010, net price 10.00") also work, but
require `AI_CORE_ENABLED=true` and valid SAP AI Core credentials in `.env` -
otherwise the agent only accepts the structured JSON shape above.

## Notes

- Header requires: `PurchaseOrderType`, `Supplier`, `CompanyCode`,
  `PurchasingOrganization`, `PurchasingGroup`, `DocumentCurrency`.
- Each item in `to_PurchaseOrderItem` requires: `PurchaseOrderItem`,
  `Material`, `Plant`, `OrderQuantity`, `PurchaseOrderQuantityUnit`,
  `NetPriceAmount`. `StorageLocation`, `NetPriceQuantity`, and
  `DocumentCurrency` are optional per item.
- `OrderQuantity`, `NetPriceAmount`, and `NetPriceQuantity` are stringified
  automatically if passed as numbers - this Gateway's OData v2 JSON rejects
  bare numeric literals for `Edm.Decimal`/`Edm.Quantity` fields.
- `S4_SAP_CLIENT` (e.g. `100`) is appended as `?sap-client=...` on every
  request (GET, CSRF fetch, and the create POST) when set - required by
  Gateway systems that don't pin the client on the destination itself.
