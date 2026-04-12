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

## Platform adapters

| Adapter              | Role                                      | Default mode   |
|---------------------|--------------------------------------------|----------------|
| `PalantirFoundryAdapter` | OSDK-shaped writes/reads + `object_type_map` | Simulation     |
| `FabricIQAdapter`      | IQ / workspace REST-shaped calls           | Simulation     |
| `MCPAdapter`           | JSON-RPC `tools/call` to any MCP server    | Simulation     |

## Running the demos

```bash
python examples/demo_validation.py
python examples/demo_portability.py
python examples/demo_migration_check.py
```

## Adding your own adapter

See [docs/adding_adapters.md](docs/adding_adapters.md).

## Related articles

- Medium (forthcoming): *Vendor-neutral semantics between Foundry, Fabric IQ, and MCP* — link TBD.

---

Part of the OntoArc enterprise ontology toolkit.
