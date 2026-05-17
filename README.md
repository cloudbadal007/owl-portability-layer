# owl-portability-layer

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#)

**Vendor-neutral OWL/SHACL semantic layer for enterprise AI platforms**

## Problem

Enterprise ontology features are increasingly bundled into proprietary stacks—Palantir Foundry and Microsoft Fabric IQ ship rich models, but teams get locked into vendor-specific object APIs, action types, and lakehouse quirks. Agent layers (MCP, A2A) need a stable semantic contract that survives platform churn.

## Architecture

```
                    ┌──────────────────────────────┐
                    │  Agents (MCP / A2A / custom)  │
                    └───────────────┬──────────────┘
                                    │
                    ┌───────────────▼──────────────┐
                    │   OWL Portability Layer      │
                    │   OWL + SHACL (pyshacl/RDFS) │
                    └───────┬──────────────┬───────┘
                            │              │
              ┌─────────────▼──┐    ┌──────▼──────────┐
              │ Palantir       │    │ Microsoft       │
              │ Foundry        │    │ Fabric IQ       │
              └────────────────┘    └─────────────────┘
                            │
                    ┌───────▼────────┐
                    │ MCP (JSON-RPC) │  ← vendor-free path
                    └────────────────┘
```

## Quick start

```bash
pip install -r requirements.txt
python examples/demo_validation.py
```

## How it works

- **Ontology first**: Domain classes and properties live in `ontologies/*.ttl` as the single semantic source of truth.
- **SHACL as policy**: Constraints (including SPARQL-based rules) enforce approvals and thresholds without scattering logic in adapters.
- **Dict → RDF**: Payloads are lifted to RDF for validation, then passed unchanged to adapters when validation passes.
- **Pluggable targets**: Register `PalantirFoundryAdapter`, `FabricIQAdapter`, or `MCPAdapter` under short keys; swap `target_platform` only.

## Platform Adapters

| Platform | Adapter | Status | Policy Model |
|---|---|---|---|
| Palantir Foundry | `PalantirFoundryAdapter` | ✅ Live | Proprietary OSDK |
| Microsoft Fabric IQ | `FabricIQAdapter` | ✅ Live | Semantic contracts |
| Google Knowledge Catalog | `GoogleKnowledgeCatalogAdapter` | ✅ Live | schema.org + RDF |
| ServiceNow Context Engine | `ServiceNowContextEngineAdapter` | ✅ Live | CMDB Knowledge Graph |
| AWS AgentCore | `AgentCoreSemanticAdapter` | ✅ Live | Cedar + OWL/SHACL |

All adapters work in simulation mode — zero platform credentials
needed to run the demos.

## Cedar + OWL/SHACL: Two Complementary Layers

AWS AgentCore ships Cedar for access control governance. The
`AgentCoreSemanticAdapter` adds the OWL/SHACL domain constraint
layer that Cedar cannot express.

| Question | Cedar (AgentCore Gateway) | OWL/SHACL (This Layer) |
|---|---|---|
| Is this principal permitted to call this tool? | ✅ | — |
| Does this call violate domain business rules? | — | ✅ |
| Does this work cross-platform? | Gateway only | ✅ All platforms |

```bash
# Cedar + OWL/SHACL parallel governance demo (zero credentials)
python examples/demo_agentcore_parallel_governance.py

# Five-platform portability demo (simulation mode)
python examples/demo_five_platform_portability.py
```

## Cross-Platform Validators

| Validator | Use Case | Demo |
|---|---|---|
| `CrossPlatformOffboardingValidator` | Employee offboarding across ServiceNow + Salesforce + Microsoft | `examples/demo_offboarding_validation.py` |

## Running the demos

```bash
python examples/demo_validation.py
python examples/demo_portability.py
python examples/demo_migration_check.py

# Cross-platform offboarding validation (zero credentials)
python examples/demo_offboarding_validation.py

# Four-platform portability demo (simulation mode)
python examples/demo_four_platform_portability.py
```

AgentCore demos are listed under [Cedar + OWL/SHACL](#cedar--owlshacl-two-complementary-layers) above.

## Adding your own adapter

See [docs/adding_adapters.md](docs/adding_adapters.md).

## Related articles

- Medium (forthcoming): *Vendor-neutral semantics between Foundry, Fabric IQ, and MCP* — link TBD.
- ServiceNow vs Microsoft vs Salesforce: The Semantic Layer War
  [MEDIUM ARTICLE LINK — add when published]
- AWS Built AgentCore With 6 Enterprise Layers. The Semantic
  Authority Layer Isn't One of Them
  [MEDIUM ARTICLE LINK — add when published]

---

Part of the OntoArc enterprise ontology toolkit.
