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
                          └───────────────┬──────────────┘
                                          │
   ┌──────────┬──────────┬──────────┬──────┼──────┬──────────┬──────────┬──────────┐
   │          │          │          │      │      │          │          │          │
┌──▼─────┐ ┌──▼──────┐ ┌──▼────┐ ┌──▼─────┐ ┌──▼───┐ ┌──▼────┐ ┌──▼─────┐ ┌──▼─────┐
│ OpenAI │ │IBM      │ │Data-  │ │Agent-  │ │Serv- │ │Google  │ │Fabric  │ │Palantir│
│Frontier│ │watsonx  │ │verse  │ │Core    │ │iceNow│ │Catalog │ │IQ      │ │Foundry │
└────────┘ └─────────┘ └───────┘ └────────┘ └──────┘ └───────┘ └────────┘ └────────┘
                                          │
                                 ┌────────▼────────┐
                                 │ MCP (JSON-RPC)  │  ← vendor-free path
                                 └─────────────────┘
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

| Platform | Adapter | Status | Semantic Model |
|---|---|---|---|
| OpenAI Frontier | `OpenAIFrontierAdapter` | ✅ Live | Business Context + OWL/SHACL |
| Palantir Foundry | `PalantirFoundryAdapter` | ✅ Live | Proprietary OSDK |
| Microsoft Fabric IQ | `FabricIQAdapter` | ✅ Live | Semantic contracts |
| Microsoft Dataverse | `DataverseSemanticAdapter` | ✅ Live | Vector index + Business Skills |
| Google Knowledge Catalog | `GoogleKnowledgeCatalogAdapter` | ✅ Live | schema.org + RDF |
| ServiceNow Context Engine | `ServiceNowContextEngineAdapter` | ✅ Live | CMDB Knowledge Graph |
| AWS AgentCore | `AgentCoreSemanticAdapter` | ✅ Live | Cedar + OWL/SHACL |
| IBM watsonx.data Context | `IBMWatsonxContextAdapter` | ✅ Live | Runtime governance + OWL/SHACL |
| Salesforce Agentforce | *(coming soon)* | 🔜 | Einstein Trust Layer |

All adapters work in simulation mode — zero credentials needed.

## OpenAI Frontier + OWL/SHACL: Three-Layer Governance

OpenAI Frontier ships Business Context and identity/permissions. The
`OpenAIFrontierAdapter` adds the OWL/SHACL constraint proof layer that
Frontier cannot express.

| Layer | Question | OpenAI Frontier | OWL/SHACL (This Layer) |
|---|---|---|---|
| 1 — Business Context | What does this entity mean? | ✅ | — |
| 2 — Identity + Permissions | Who can call which action? | ✅ | — |
| 3 — Constraint Proof | Are formal domain rules satisfied? | — | ✅ |

| Dimension | OpenAI Frontier | Google Knowledge Catalog | Microsoft Fabric IQ |
|---|---|---|---|
| Business accessibility | ✅ Best | Moderate | Moderate |
| Open standards | Moderate | ✅ Best | Moderate |
| OWL support | ❌ | ❌ | ❌ |
| SHACL support | ❌ | ❌ | ❌ |
| Production status | GA (pricing change July 6) | GA | GA |

See `docs/openai_frontier_vs_google_vs_microsoft.md` for full analysis.

```bash
# OpenAI Frontier + OWL/SHACL three-layer governance demo (zero credentials)
python examples/demo_frontier_governance.py

# Nine-platform portability demo (simulation mode)
python examples/demo_nine_platform_portability.py
```

## IBM vs Google vs AWS: Three Approaches to the Semantic Layer

| Dimension | Google Knowledge Catalog | AWS AgentCore | IBM watsonx.data |
|---|---|---|---|
| Governance model | Retrieval-first | Cedar (access control) | Runtime enforcement |
| Cross-platform | ❌ | Gateway only | Federated ✅ |
| Open standards | RDF/JSON-LD ✅ | Cedar (open source) ✅ | Claimed ✅ |
| OWL support | ❌ | ❌ | ❌ |
| SHACL support | ❌ | ❌ | ❌ |
| Production status | GA | GA | Private preview |

See `docs/ibm_vs_google_vs_aws.md` for full analysis.

## Microsoft's Two Semantic Layers

Microsoft offers two complementary semantic layers. The OWL Portability
Layer includes adapters for both:

| Layer | Adapter | Data Estate | Entry Barrier |
|---|---|---|---|
| Fabric IQ | `FabricIQAdapter` | OneLake / DirectLake | Requires Fabric migration |
| Dataverse | `DataverseSemanticAdapter` | Dynamics 365, Power Apps, M365 | Already deployed at scale |

See `docs/dataverse_vs_fabric_iq.md` for the full comparison.

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

# Dataverse + OWL/SHACL bridge demo (zero credentials)
python examples/demo_dataverse_bridge.py

# Six-platform portability demo (simulation mode)
python examples/demo_six_platform_portability.py
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

# Dataverse + OWL/SHACL bridge demo (zero credentials)
python examples/demo_dataverse_bridge.py

# Six-platform portability demo (simulation mode)
python examples/demo_six_platform_portability.py

# IBM watsonx + OWL/SHACL governance demo (zero credentials)
python examples/demo_ibm_watsonx_governance.py

# Seven-platform portability demo (simulation mode)
python examples/demo_seven_platform_portability.py

# OpenAI Frontier + OWL/SHACL three-layer governance demo
python examples/demo_frontier_governance.py

# Nine-platform portability demo (simulation mode)
python examples/demo_nine_platform_portability.py
```

AgentCore demos are listed under [Cedar + OWL/SHACL](#cedar--owlshacl-two-complementary-layers) above.

## Running tests

All tests run offline in simulation mode — zero credentials required.

```bash
pip install -r requirements.txt

# OpenAI Frontier adapter (16 tests)
pytest tests/test_openai_frontier_adapter.py -v

# Nine-platform portability integration (5 tests)
pytest tests/test_nine_platform_portability.py -v

# Full suite
pytest tests/ -v
```

| Test module | Coverage |
|---|---|
| `test_openai_frontier_adapter.py` | Frontier denial, SHACL block, both pass, mapping, demo cases |
| `test_nine_platform_portability.py` | Identical SHACL across 8 live platforms + Salesforce validate_only |
| `test_adapters.py` | Simulation smoke tests including OpenAI Frontier |
| `test_ibm_watsonx_adapter.py` | IBM runtime governance + SHACL |
| `test_agentcore_adapter.py` | Cedar + SHACL |
| `test_dataverse_adapter.py` | Dataverse grounding + SHACL |

## Adding your own adapter

See [docs/adding_adapters.md](docs/adding_adapters.md).

## Related articles

- Microsoft Just Shipped Two Semantic Layers. One of Them Is
  Quietly More Powerful Than Fabric IQ
  [MEDIUM ARTICLE LINK — add when published]
- [Google vs Microsoft vs Palantir: The Enterprise Ontology Race and the Layer All Three Are Missing](https://medium.com/@cloudpankaj/google-vs-microsoft-vs-palantir-the-enterprise-ontology-race-and-the-layer-all-three-are-missing-e965b2d635d9)
- [ServiceNow vs Microsoft vs Salesforce: The Semantic Layer War (and the OWL Layer None of Them Ship)](https://medium.com/@cloudpankaj/servicenow-vs-microsoft-vs-salesforce-the-semantic-layer-war-and-the-owl-layer-none-of-them-ship-d3c4b2eb4949)
- [AWS Built AgentCore With 6 Enterprise Layers. The Semantic Authority Layer Isn't One of Them](https://medium.com/@cloudpankaj/aws-built-agentcore-with-6-enterprise-layers-the-semantic-authority-layer-isnt-one-of-them-72c9373388b9)
- IBM watsonx vs Google Knowledge Catalog vs AWS AgentCore:
  The Semantic Layer Race Just Got a New Contender — and a New Gap
  [MEDIUM ARTICLE LINK — add when published]
- OpenAI Frontier vs Google Knowledge Catalog vs Microsoft Fabric IQ:
  The Semantic Layer Battle Just Got Its Biggest Contender
  [MEDIUM ARTICLE LINK — add when published]

See also:

- `docs/openai_frontier_vs_google_vs_microsoft.md` — three-way semantic layer comparison
- `docs/ibm_vs_google_vs_aws.md` — IBM vs Google vs AWS comparison
- `docs/architecture.md` — nine-platform architecture and governance layers

---

Part of the OntoArc enterprise ontology toolkit.
