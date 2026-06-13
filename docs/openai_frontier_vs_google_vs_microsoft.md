# OpenAI Frontier vs Google Knowledge Catalog vs Microsoft Fabric IQ: The Three-Way Semantic Layer Comparison

> Part of the enterprise ontology governance stack.

## 1. Overview

By mid-2026, three hyperscalers represent the three dominant approaches to
enterprise semantic layers for AI agents:

- **OpenAI Frontier** optimized for **business accessibility** — the fastest
  path from zero to a governed "AI co-worker" that understands your
  organisation's entities, workflows, and permissions.
- **Google Knowledge Catalog** optimized for **open-standards retrieval** —
  describe everything in RDF/JSON-LD and let agents find it at scale.
- **Microsoft Fabric IQ** optimized for **formal domain modelling** inside
  the analytics estate — semantic contracts bound to DirectLake and OneLake.

They are not three implementations of one idea. They are three different
ideas about where the semantic layer should live and what it should enforce.
And all three share one gap: none enforces formal, machine-checkable domain
**proofs**. That is the gap the OWL Portability Layer fills.

## 2. OpenAI Frontier

**Business Context layer.** Frontier's core value is making enterprise
semantics accessible. Business Context tells agents what entities mean in
your organisation — not just what columns are called, but what workflows
they participate in and who owns them.

**Four components.** Frontier ships Business Context (entity meaning),
agent identity, permission boundaries, and workflow mapping. Together they
form an "AI co-worker" governance model: the agent understands the business,
knows who it is, and operates within defined boundaries.

**The accessibility trade-off.** Frontier is the most approachable setup of
the three — but accessibility is not formal constraint enforcement. Business
Context can know that a ComplianceHold involves Legal Approval without
requiring a recorded approver before release.

**July 6 pricing deadline.** OpenAI Frontier workspace agents move to
credit-based pricing on July 6, 2026. Enterprise architects evaluating
Frontier should design the OWL/SHACL constraint layer before go-live, not
after.

## 3. Google Knowledge Catalog

**Open standards strength.** Google leans on RDF and JSON-LD with
schema.org vocabularies. Entities are described in a portable,
vendor-neutral format — the best of the three at semantic retrieval at
scale.

**MCP integration.** Knowledge Catalog integrates with the Model Context
Protocol, making entity context available to agents through a standard
tooling interface.

**Retrieval, not enforcement.** Knowledge Catalog answers "what is this and
what is it related to?" extremely well. It does not answer "is this action
permitted by domain rules?" RDF tells you a `ComplianceHold` exists. It does
not tell you that releasing one without a recorded approver is forbidden.

## 4. Microsoft Fabric IQ

**Closest to formal domain modelling.** Fabric IQ semantic contracts model
domain entities, relationships, and Permitted Actions — the closest any
platform comes to expressing what agents may do with data inside the
analytics estate.

**DirectLake constraint.** Fabric IQ's semantic layer is bound to the
DirectLake / OneLake boundary. It excels for analytics agents operating
inside Fabric; cross-estate portability requires additional bridging.

**Permitted Actions.** Fabric IQ can express which actions are allowed on
which entity types — but Permitted Actions are not OWL class constraints or
SHACL shape validation. They govern intent inside Fabric, not formal proofs
portable across platforms.

## 5. Comparison

| Dimension | OpenAI Frontier | Google Knowledge Catalog | Microsoft Fabric IQ |
|---|---|---|---|
| Business accessibility | ✅ Best | Moderate | Moderate |
| Open standards | Moderate | ✅ Best (RDF/JSON-LD) | Moderate |
| Formal constraint | ❌ | ❌ | ❌ |
| Cross-platform | Moderate | Moderate | DirectLake bound |
| MCP | Via ecosystem | ✅ Native | Via ecosystem |
| OWL | ❌ | ❌ | ❌ |
| SHACL | ❌ | ❌ | ❌ |
| Production status | GA (pricing change July 6) | GA | GA |

## 6. The three-layer governance model

All three platforms need an OWL/SHACL layer added on top:

| Layer | Question | OpenAI | Google | Microsoft |
|---|---|---|---|---|
| 1 — Business Context | What does this entity mean? | ✅ | ✅ | ✅ |
| 2 — Identity + Permissions | Who can call which action? | ✅ | Partial | ✅ (Permitted Actions) |
| 3 — OWL/SHACL Constraint Proof | Are formal constraints satisfied? | ❌ Build | ❌ Build | ❌ Build |

**Layer 1** is semantic understanding — all three ship it well.
**Layer 2** is access control — Frontier and Fabric IQ ship it; Google is
retrieval-focused.
**Layer 3** is formal constraint proof — none of the three ship it. That is
what the OWL Portability Layer provides.

The critical gap: Business Context can understand that a ComplianceHold
requires Legal approval without enforcing that `holdApprovedBy` is present.
Understanding does not equal formal constraint enforcement.

## 7. Pricing note

OpenAI Frontier workspace agents move to credit-based pricing on July 6,
2026. Teams adopting Frontier should:

1. Design OWL ontologies and SHACL shapes before the pricing transition.
2. Run the constraint layer in simulation mode during architecture review.
3. Treat Layer 3 as a go-live requirement, not a post-deployment afterthought.

## 8. Code example

Register the Frontier adapter alongside existing platform adapters:

```python
from owl_portability.adapters.openai_frontier import OpenAIFrontierAdapter
from owl_portability.layer import OWLPortabilityLayer

layer = OWLPortabilityLayer(
    "ontologies/procurement.ttl",
    "ontologies/procurement_shacl.ttl",
)

layer.register_adapter(
    "openai_frontier",
    OpenAIFrontierAdapter(
        ontology_path="ontologies/procurement.ttl",
        shacl_path="ontologies/procurement_shacl.ttl",
        frontier_api_key="",
        frontier_org_id="",
        simulation_mode=True,
    ),
)

# Frontier governance + OWL/SHACL three-layer demo (zero credentials)
# python examples/demo_frontier_governance.py
```

## 9. Testing

```bash
pytest tests/test_openai_frontier_adapter.py -v
pytest tests/test_nine_platform_portability.py -v
pytest tests/ -v
```

Key test cases in `tests/test_openai_frontier_adapter.py`:

| Test | Verifies |
|---|---|
| `test_frontier_denied_skips_shacl` | Frontier denial short-circuits SHACL |
| `test_frontier_permitted_shacl_blocks` | Business Context ≠ constraint enforcement |
| `test_both_layers_pass` | All three governance layers pass |
| `test_demo_case_*` | Mirrors `demo_frontier_governance.py` scenarios |

---

Part of the enterprise ontology governance stack.
