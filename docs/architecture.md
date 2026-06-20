# Architecture

## High-level view

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent orchestration (MCP, A2A, custom agents)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  OWL Portability Layer                                          │
│  • Load OWL + SHACL (rdflib)                                    │
│  • validate_only / validate_and_route                           │
│  • pyshacl + RDFS inference                                     │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
    ┌────────▼────────┐             ┌────────▼────────┐
    │  OpenAI         │             │  IBM watsonx    │
    │  Frontier       │             │  Context        │
    │  (Business      │             │  (runtime       │
    │   Context)      │             │   governance)   │
    └────────┬────────┘             └────────┬────────┘
             │                               │
    ┌────────▼────────┐             ┌────────▼────────┐
    │  Palantir       │             │  Fabric IQ      │
    │  Foundry        │             │  (DirectLake /  │
    │  (OSDK-shaped)  │             │   IQ REST)      │
    └─────────────────┘             └─────────────────┘
             │
    ┌────────▼────────┐
    │  MCPAdapter     │  ← vendor-free JSON-RPC to any MCP server
    └─────────────────┘
```

Nine platform adapters are registered today (eight live, Salesforce coming soon).
Each adapter runs the **same** SHACL shapes from `ontologies/procurement_shacl.ttl`.
Platform-specific governance (Frontier Business Context, Cedar, IBM runtime policy)
runs in the adapter layer; formal constraint proof runs in OWL/SHACL.

## Data flow

1. **Ingest**: Application builds a dict aligned with ontology property local names (`paymentId`, `hasHoldStatus`, nested objects with `@type`).
2. **Lift**: `dict_to_entity_graph` produces a small RDF graph merged with the ontology for reasoning.
3. **Validate**: `pyshacl.validate` runs with `inference='rdfs'` so subclasses (e.g. `ComplianceHold` ⊑ `HoldStatus`) are visible to shapes.
4. **Route**: On success, the registered `BaseAdapter.write` runs for the chosen platform key.

## Two-layer vs three-layer governance

Some adapters implement **two-layer** governance (platform policy + OWL/SHACL):

| Adapter | Layer 1 (platform) | Layer 2 (OWL/SHACL) |
|---|---|---|
| `OpenAIFrontierAdapter` | Frontier Business Context + permissions | SHACL constraint proof |
| `AgentCoreSemanticAdapter` | Cedar (Gateway access control) | SHACL constraint proof |
| `IBMWatsonxContextAdapter` | watsonx runtime governance | SHACL constraint proof |
| `DataverseSemanticAdapter` | Dataverse semantic grounding | SHACL constraint proof |

OpenAI Frontier is the reference **three-layer** model:

1. **Business Context** — what does this entity mean?
2. **Identity + Permissions** — who can call which action?
3. **OWL/SHACL** — are formal domain constraints satisfied? (this layer)

See `docs/openai_frontier_vs_google_vs_microsoft.md` for the three-way comparison.

## Why OWL + SHACL in the middle

- **Portability**: The same shapes run in CI, pre-flight tools, and runtime—no forked “rules as code” per vendor.
- **Auditability**: Violation reports come from SHACL with stable `sh:message` text.
- **Migration**: Mapping Palantir Object Types or Fabric IQ entities to OWL classes is explicit and testable (see `examples/demo_migration_check.py`).

## Testing

```bash
pytest tests/test_openai_frontier_adapter.py -v
pytest tests/test_nine_platform_portability.py -v
pytest tests/
```

All tests run offline in simulation mode — zero platform credentials required.
