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
    │  Palantir       │             │  Fabric IQ      │
    │  Foundry        │             │  (DirectLake /  │
    │  (OSDK-shaped)  │             │   IQ REST)      │
    └─────────────────┘             └─────────────────┘
             │
    ┌────────▼────────┐
    │  MCPAdapter     │  ← vendor-free JSON-RPC to any MCP server
    └─────────────────┘
```

The semantic contract lives in `ontologies/` (OWL classes and SHACL shapes). Python code does not encode business rules in conditionals; it lifts payloads to RDF and delegates policy to SHACL. Adapters translate validated dicts into platform-specific APIs without changing validation logic.

## Data flow

1. **Ingest**: Application builds a dict aligned with ontology property local names (`paymentId`, `hasHoldStatus`, nested objects with `@type`).
2. **Lift**: `dict_to_entity_graph` produces a small RDF graph merged with the ontology for reasoning.
3. **Validate**: `pyshacl.validate` runs with `inference='rdfs'` so subclasses (e.g. `ComplianceHold` ⊑ `HoldStatus`) are visible to shapes.
4. **Route**: On success, the registered `BaseAdapter.write` runs for the chosen platform key.

## Why OWL + SHACL in the middle

- **Portability**: The same shapes run in CI, pre-flight tools, and runtime—no forked “rules as code” per vendor.
- **Auditability**: Violation reports come from SHACL with stable `sh:message` text.
- **Migration**: Mapping Palantir Object Types or Fabric IQ entities to OWL classes is explicit and testable (see `examples/demo_migration_check.py`).
