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
└────────────┬────────────────────────────────────────────────────┘
             │
   ┌─────────┼─────────┬─────────┬─────────┬─────────┐
   │         │         │         │         │         │
┌──▼──┐  ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│Grok │  │OpenAI │ │ IBM   │ │Data-  │ │Agent  │ │Service│
│on DB│  │Front. │ │watsonx│ │verse  │ │Core   │ │  Now  │
│Genie│  │Bus.   │ │runtime│ │Skills │ │Cedar  │ │CMDB   │
│+UAI │  │Context│ │gov.   │ │+vec.  │ │+OWL   │ │graph  │
└─────┘  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘
   ┌─────────┬─────────┬─────────┬─────────┐
   │         │         │         │         │
┌──▼────┐ ┌──▼────┐ ┌──▼────┐ ┌──▼────┐
│Google │ │Fabric │ │Palantir│ │  MCP  │
│Catalog│ │  IQ   │ │Foundry │ │Adapter│
│schema │ │Direct │ │  OSDK  │ │JSON-  │
│.org   │ │ Lake  │ │        │ │ RPC   │
└───────┘ └───────┘ └────────┘ └───────┘
```

Nine platform adapters are registered today. Each adapter runs the **same**
SHACL shapes from `ontologies/procurement_shacl.ttl`. Platform-specific
governance (Genie Ontology + Unity AI Gateway, Frontier Business Context,
Cedar, IBM runtime policy) runs in the adapter layer; formal constraint proof
runs in OWL/SHACL. `MCPAdapter` provides a vendor-free JSON-RPC path alongside
the nine vendor adapters.

## Data flow

1. **Ingest**: Application builds a dict aligned with ontology property local names (`paymentId`, `hasHoldStatus`, nested objects with `@type`).
2. **Lift**: `dict_to_entity_graph` produces a small RDF graph merged with the ontology for reasoning.
3. **Validate**: `pyshacl.validate` runs with `inference='rdfs'` so subclasses (e.g. `ComplianceHold` ⊑ `HoldStatus`) are visible to shapes.
4. **Route**: On success, the registered `BaseAdapter.write` runs for the chosen platform key.

## Two-layer vs three-layer governance

Some adapters implement **two-layer** governance (platform policy + OWL/SHACL):

| Adapter | Layer 1 (platform) | Layer 2 (OWL/SHACL) |
|---|---|---|
| `GrokDatabricksAdapter` | Genie Ontology + Unity AI Gateway | SHACL constraint proof |
| `OpenAIFrontierAdapter` | Frontier Business Context + permissions | SHACL constraint proof |
| `AgentCoreSemanticAdapter` | Cedar (Gateway access control) | SHACL constraint proof |
| `IBMWatsonxContextAdapter` | watsonx runtime governance | SHACL constraint proof |
| `DataverseSemanticAdapter` | Dataverse semantic grounding | SHACL constraint proof |

OpenAI Frontier and Grok-on-Databricks are reference **three-layer** models:

1. **Semantic context** — what does this entity mean? (Business Context / Genie Ontology)
2. **Access control** — who can call which action? (Frontier permissions / Unity AI Gateway)
3. **OWL/SHACL** — are formal domain constraints satisfied? (this layer)

On Grok-on-Databricks, the reasoning model (Grok, GPT, Claude on Agent Bricks) is
orthogonal to layers 1–3 — it is audit metadata, not a governance layer.

See `docs/openai_frontier_vs_google_vs_microsoft.md` and
`docs/grok_databricks_naming_convergence.md` for platform comparisons.

## KYC extraction pipeline

The companion adapter in `adapters/kyc_extraction/` builds compliance ontologies
from enterprise source systems before they enter the portability layer.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Oracle DDL   │  │ Confluence   │  │    Slack     │  │  Salesforce  │  │   MongoDB    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │                 │
       └─────────────────┴────────┬────────┴─────────────────┴─────────────────┘
                                  ▼
                    ┌─────────────────────────────┐
                    │  LLM-assisted extraction    │
                    │  ASSUMPTION + SOURCE tags   │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │  merge_deduplicator.py      │
                    │  Canonical vocabulary TTL   │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │  validator.py               │
                    │  OWL consistency + SHACL    │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │  OWL Portability Layer      │
                    │  nine platform adapters     │
                    └─────────────────────────────┘
```

| Module | Role |
|---|---|
| `oracle_ddl_parser.py` | DDL → OWL class candidates |
| `confluence_chunker.py` | Policy sections → axiom candidates |
| `slack_filter.py` | Conflict detection + filtered axioms |
| `merge_deduplicator.py` | Synonym clustering → canonical Turtle |
| `validator.py` | OWL consistency, SHACL, expert review report |
| `kyc_sample.ttl` | Reference KYC ontology fragment |

## Why OWL + SHACL in the middle

- **Portability**: The same shapes run in CI, pre-flight tools, and runtime—no forked “rules as code” per vendor.
- **Auditability**: Violation reports come from SHACL with stable `sh:message` text.
- **Migration**: Mapping Palantir Object Types or Fabric IQ entities to OWL classes is explicit and testable (see `examples/demo_migration_check.py`).

## Testing

```bash
pytest tests/test_grok_databricks_adapter.py -v
pytest tests/test_openai_frontier_adapter.py -v
pytest tests/test_nine_platform_portability.py -v
pytest tests/test_kyc_extraction.py -v
pytest tests/
```

All tests run offline in simulation mode — zero platform credentials required.
