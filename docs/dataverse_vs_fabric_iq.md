# Microsoft's Two Semantic Layers: Dataverse vs Fabric IQ

## Overview

Microsoft ships two complementary semantic layers for enterprise AI agents. They
serve different data estates, agent patterns, and migration paths. The OWL
Portability Layer includes adapters for both because enterprises rarely choose
just one — operational agents live in Dataverse today; analytics agents migrate
toward Fabric IQ over time.

Use **Dataverse** when your agents must act on Dynamics 365, Power Apps, and
Microsoft 365 operational data that is already deployed at scale. Use **Fabric
IQ** when your agents need analytics-grade semantic models over OneLake with
DirectLake-backed query performance.

Neither layer provides formal OWL/SHACL constraint enforcement. Both benefit
from a vendor-neutral governance layer that runs before agent actions execute.

## Fabric IQ

**What it does:** Fabric IQ exposes semantic contracts over OneLake data —
entity types, relationships, and analytics-oriented business meaning for agents
that query and reason over lakehouse data.

**DirectLake constraint:** Some graph and semantic workloads depend on
DirectLake-backed stores. Teams must plan for Fabric migration and lakehouse
topology before IQ semantic models deliver full value.

**Who should use it:** Analytics agents, copilots over enterprise data lakes,
and teams already committed to Microsoft Fabric as their analytics platform.

**Adapter:** `FabricIQAdapter` — simulation-first HTTP integration with Fabric
IQ workspace APIs.

## Dataverse Agent Data Platform

**What it does:** Dataverse provides an intelligent semantic layer for
operational agents — schema graph traversal, entity relationships, Business
Skills (procedural knowledge from workflows), and MCP Server integration for
dynamic schema discovery.

**Business Skills:** Skills ground agents in approval workflows, policy context,
and domain procedures that live in Dynamics 365 and Power Platform.

**MCP Server:** Agents query live schema and relationship metadata without
hard-coding table names or field mappings.

**Who should use it:** Finance, procurement, and line-of-business agents
deployed on Dynamics 365, Power Apps, Copilot Studio, and Microsoft 365 —
especially where Dataverse is already the system of record.

**Adapter:** `DataverseSemanticAdapter` — two-layer validation combining
Dataverse semantic grounding with OWL/SHACL formal constraints.

## Comparison

| Dimension | Fabric IQ | Dataverse Agent Data Platform |
|---|---|---|
| **Data foundation** | OneLake / lakehouse | Dynamics 365 / Power Platform / M365 |
| **Binding constraint** | DirectLake migration path | Already deployed at enterprise scale |
| **Semantic model** | Analytics semantic contracts | Vector index + Business Skills |
| **Agent patterns** | Analytics copilots, data agents | Operational agents, workflow automation |
| **Procedural knowledge** | Limited — analytics-focused | Business Skills from live workflows |
| **MCP** | Emerging | MCP Server for schema discovery |
| **Scale** | Requires Fabric adoption | Millions of production deployments |
| **Write-back** | Analytics-oriented | Full CRUD on operational entities |
| **Entry barrier** | Requires Fabric migration | Low — already in most Microsoft estates |

## Hybrid architecture

Many enterprises run both layers simultaneously:

- **Dataverse** grounds operational agents that release holds, update vendors,
  and execute workflow actions against live CRM and ERP records.
- **Fabric IQ** grounds analytics agents that forecast spend, detect anomalies,
  and recommend actions over historical lakehouse data.

Microsoft Agent Framework 1.0 can orchestrate agents across both layers — routing
operational tasks to Dataverse-grounded agents and analytical tasks to Fabric
IQ-grounded agents. The OWL/SHACL portability layer sits above both, enforcing
identical domain constraints regardless of which semantic layer supplied the
business context.

## Adding OWL/SHACL

Neither Fabric IQ nor Dataverse enforces formal OWL class constraints or SHACL
shapes. They understand that a record is a ComplianceHold; they cannot formally
block release when `holdApprovedBy` is absent.

The OWL Portability Layer completes the governance picture:

| Layer | Question answered |
|---|---|
| Dataverse / Fabric IQ | *What does this entity mean in business terms?* |
| OWL/SHACL | *Is this action formally permitted given domain policy?* |

Understanding ≠ permission. Microsoft ships the understanding. You build the
governance.

## Code example

Register the Dataverse adapter alongside existing platform adapters:

```python
from owl_portability.adapters.dataverse import DataverseSemanticAdapter

layer.register_adapter(
    "dataverse",
    DataverseSemanticAdapter(
        ontology_path="ontologies/procurement.ttl",
        shacl_path="ontologies/procurement_shacl.ttl",
        simulation_mode=True,
    ),
)
```

See `examples/demo_dataverse_bridge.py` for the full two-layer validation demo
and `examples/demo_six_platform_portability.py` for cross-platform portability.

