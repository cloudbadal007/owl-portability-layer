# Nine Platforms, Nine Names, One Gap: The Semantic Layer Naming Convergence

## Overview

Every major enterprise AI platform has independently arrived at language describing the same architectural ambition: give agents a shared understanding of business entities, map natural-language queries to structured data, and govern who can act on what at runtime.

The vocabulary differs. The ambition converges. The formal constraint proof layer remains absent.

## The naming table

| Platform | Vendor semantic layer name | Adapter |
|---|---|---|
| Databricks | Genie Ontology + Unity AI Gateway | `GrokDatabricksAdapter` |
| OpenAI | Business Context / semantic layer for the enterprise | `OpenAIFrontierAdapter` |
| Google | Knowledge Catalog | `GoogleKnowledgeCatalogAdapter` |
| Microsoft (Fabric) | Semantic Contracts (Fabric IQ) | `FabricIQAdapter` |
| Microsoft (Dataverse) | Business Skills | `DataverseSemanticAdapter` |
| IBM | watsonx.data Context | `IBMWatsonxContextAdapter` |
| AWS | Cedar (policy, not semantic per se, but governs the same boundary) | `AgentCoreSemanticAdapter` |
| Palantir | Ontology (the original, predates this wave) | `PalantirFoundryAdapter` |
| ServiceNow | Context Engine | `ServiceNowContextEngineAdapter` |

Nine platforms. Nine vendor adapters. One recurring pattern.

## What's common across all nine

- **Context resolution** — mapping agent queries to business entities and relationships
- **Business term mapping** — bridging natural language to structured data models
- **Runtime access control** — deciding which agent identities can invoke which tools or actions

These three capabilities appear under different names but solve the same class of problem: help agents understand and access enterprise data safely.

## What's absent across all nine

- **Formal OWL class hierarchies** — machine-readable ontologies with explicit subclass relationships
- **SHACL constraint validation** — provable enforcement of domain rules (approvals, thresholds, mandatory fields)
- **Machine-readable constraint proof** — auditable evidence that an action satisfies formal business rules

No platform in the matrix ships all three. Understanding an entity is not the same as proving it satisfies a constraint.

## Why this convergence matters

Independent arrival at the same framing from nine different vendors is strong evidence the industry recognises the problem. Every major stack is building a semantic layer. Every major stack stops short of formal constraint proof.

The solution gap is the opportunity. Teams that own OWL/SHACL constraints today can plug them into any platform tomorrow — because the constraint layer is vendor-neutral by design.

## The model-agnostic insight

Grok-on-Databricks makes the separation explicit:

- **Genie Ontology** resolves what an entity means
- **Unity AI Gateway** decides whether an agent may act
- **Grok 4.3** (or GPT-5, or claude-opus on Agent Bricks) reasons over the context

Swapping the reasoning model does not change what Genie Ontology knows or what Unity AI Gateway permits. It also does not add formal constraint proof. The gap belongs to the platform architecture, not the model.

The `GrokDatabricksAdapter` validates entities regardless of which model reasoned about them. The `reasoning_model` field is audit metadata — it is carried through results but never affects validation logic.

## Code example

Register the Grok-on-Databricks adapter alongside any other platform:

```python
from owl_portability.adapters.grok_databricks import GrokDatabricksAdapter
from owl_portability.layer import OWLPortabilityLayer

layer = OWLPortabilityLayer(
    "ontologies/procurement.ttl",
    "ontologies/procurement_shacl.ttl",
)

layer.register_adapter(
    "grok_databricks",
    GrokDatabricksAdapter(
        ontology_path="ontologies/procurement.ttl",
        shacl_path="ontologies/procurement_shacl.ttl",
        databricks_workspace_url="",
        databricks_token="",
        simulation_mode=True,
    ),
)

result = layer.validate_and_route(
    {"paymentId": "PAY-001", "amountUSD": 25000},
    "PaymentEvent",
    target_platform="grok_databricks",
)
```

Nine platforms. One OWL/SHACL constraint layer. The governance never changes.
