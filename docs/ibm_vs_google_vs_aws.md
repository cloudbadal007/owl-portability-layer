# IBM watsonx vs Google Knowledge Catalog vs AWS AgentCore: The Three-Way Semantic Layer Comparison

## 1. Overview

By IBM Think 2026, three hyperscalers had each shipped a distinct answer to
the same enterprise question: *how do AI agents understand — and act safely
on — business data they did not create?*

Each vendor optimized for a different axis of that problem:

- **Google Knowledge Catalog** optimized for **open-standards retrieval** —
  describe everything in RDF/JSON-LD and let agents find it.
- **AWS AgentCore** optimized for **governance authoring** — give security
  teams a formally verifiable access-control language (Cedar).
- **IBM watsonx.data Context** optimized for **federated runtime
  governance** — resolve context across clouds and enforce policy as the
  action happens.

They are not three implementations of one idea. They are three different
ideas about where the semantic layer should live and what it should enforce.
And all three share one gap: none enforces formal, machine-checkable domain
**proofs**. That is the gap the OWL Portability Layer fills.

## 2. Google Knowledge Catalog

**Strength: open standards.** Google leans on RDF and JSON-LD with
schema.org vocabularies. Entities are described in a portable, vendor-neutral
format, which makes Google the best of the three at *semantic retrieval at
scale* — finding the right entity and returning rich, linked context.

**Focus: retrieval, not enforcement.** Knowledge Catalog answers "what is
this and what is it related to?" extremely well. It does not answer "is this
action permitted by domain rules?" There is no constraint engine that can
block a malformed or non-compliant action before it executes.

**The semantic gap.** Open standards describe data; they do not constrain
behavior. RDF tells you a `ComplianceHold` exists. It does not tell you that
releasing one without a recorded approver is forbidden.

## 3. AWS AgentCore (Cedar)

**Strength: governance accessibility.** AgentCore ships Cedar, an
open-source policy language that is *formally verifiable* — AWS can
mathematically reason about whether a policy permits or denies a request.
This is the most rigorous access-control story of the three, and it is
authored in a language security teams can actually read.

**Cedar's formal verifiability.** Cedar answers "is this principal permitted
to invoke this tool with these parameters?" with provable precision. That is
genuinely formal — but it is formal *about access*, not about domain
semantics.

**The gateway scope limitation.** Cedar only sees traffic that flows through
the AgentCore Gateway. Cross-platform agent-to-agent delegations — to
Salesforce, ServiceNow, or any non-AgentCore system — bypass the Gateway
entirely. The policy is sound but its blast radius stops at the AWS boundary.

## 4. IBM watsonx.data Context

**The federated claim.** IBM's pitch is the most architecturally ambitious:
a context layer that resolves meaning across clouds and data estates,
aligned with open standards, and federated rather than gateway-bound. If the
claim holds, IBM closes the cross-platform scope gap that constrains Cedar.

**Runtime governance.** watsonx.data Context claims to enforce governance *at
the moment of action* — the closest any platform has come to the OWL/SHACL
argument that constraints must run inline, not after the fact.

**Policy vs proof.** The distinction matters: IBM enforces **policies** —
configurable rules about which actions are permitted. OWL/SHACL enforces
**proofs** — constraint satisfaction that is machine-readable and auditable.
A policy can be correct and still miss a domain invariant it was never told
about. A proof is checked against the formal model itself.

**Private preview status.** As of Think 2026, watsonx.data Context is in
private preview. The architecture is the most interesting new entrant in the
seven-platform matrix, but production validation is still pending.

## 5. The Policy vs Proof Distinction

IBM's announcement highlights the gap more clearly than any prior platform,
precisely *because* it gets so close.

- A **policy** is a rule an administrator writes: "analytics agents may not
  release holds." It is enforced if and only if someone anticipated the case
  and authored the rule.
- A **proof** is a constraint derived from the domain model itself: "a
  `ComplianceHold` is invalid unless `holdApprovedBy` is present." It holds
  for *every* agent, every path, every platform — because it is a property
  of the data, not of a policy table.

IBM ships policies. They are necessary. They are not sufficient. When an
action arrives through a path no policy anticipated — an external agent, a
federated bypass, a novel tool — the policy is silent and the proof still
fires.

**IBM enforces policies. OWL/SHACL enforces proofs. Build the proofs.**

## 6. Comparison Table

| Dimension | Google Knowledge Catalog | AWS AgentCore (Cedar) | IBM watsonx.data Context |
|---|---|---|---|
| Open standards | RDF/JSON-LD ✅ | Cedar (open source) ✅ | Claimed ✅ |
| Runtime governance | ❌ (retrieval-first) | ✅ (Gateway requests) | ✅ (runtime claim) |
| Cross-platform scope | ❌ | Gateway only | Federated ✅ |
| Formal verifiability | ❌ | ✅ (Cedar) | ⚠️ Policy-based |
| OWL support | ❌ | ❌ | ❌ |
| SHACL support | ❌ | ❌ | ❌ |
| Production status | GA | GA | Private preview |
| Unique strength | Best semantic retrieval | Verifiable access control | Federated runtime governance |

## 7. When to Choose Which

| If your priority is… | Choose… | But still add… |
|---|---|---|
| Rich, portable semantic retrieval | Google Knowledge Catalog | OWL/SHACL for enforcement |
| Provable access control inside AWS | AWS AgentCore (Cedar) | OWL/SHACL for cross-platform domain proofs |
| Cross-cloud federated context + runtime policy | IBM watsonx.data Context | OWL/SHACL for formal, auditable proofs |
| Vendor-neutral domain enforcement everywhere | — | OWL Portability Layer (all of the above) |

The decision is rarely exclusive. Google retrieval, Cedar access control, and
IBM federation are complementary. The constant across all three scenarios is
the missing formal proof layer.

## 8. Adding OWL/SHACL

All three platforms deliver excellent semantic *understanding*. None delivers
formal constraint *proof*. The OWL Portability Layer completes the picture:

- A single OWL ontology defines the domain (`ontologies/procurement.ttl`).
- SHACL shapes define the constraints (`ontologies/procurement_shacl.ttl`).
- Each platform adapter runs the *same* SHACL validation, so the governance
  is identical whether the action targets Google, AWS, or IBM.

Platform governance runs first (retrieval, Cedar, or IBM runtime policy).
OWL/SHACL runs in parallel and catches the formal domain constraint the
platform layer cannot express. **Both layers are required. Neither alone is
sufficient.**

## 9. Code Example

Register all three platforms behind one OWL/SHACL constraint layer:

```python
from owl_portability.adapters.google_knowledge_catalog import (
    GoogleKnowledgeCatalogAdapter,
)
from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter
from owl_portability.adapters.ibm_watsonx import IBMWatsonxContextAdapter
from owl_portability.layer import OWLPortabilityLayer

layer = OWLPortabilityLayer(
    "ontologies/procurement.ttl",
    "ontologies/procurement_shacl.ttl",
)

layer.register_adapter(
    "google",
    GoogleKnowledgeCatalogAdapter(project_id="demo-project"),
)
layer.register_adapter(
    "agentcore",
    AgentCoreSemanticAdapter(
        ontology_path="ontologies/procurement.ttl",
        shacl_path="ontologies/procurement_shacl.ttl",
        simulation_mode=True,
    ),
)
layer.register_adapter(
    "ibm_watsonx",
    IBMWatsonxContextAdapter(
        ontology_path="ontologies/procurement.ttl",
        shacl_path="ontologies/procurement_shacl.ttl",
        watsonx_url="https://your-instance.cloud.ibm.com",
        simulation_mode=True,
    ),
)

# The SHACL constraint is identical across all three.
# Change target_platform. The governance never changes.
result = layer.validate_and_route(
    {"paymentId": "PAY-001", "amountUSD": 25000},
    "PaymentEvent",
    target_platform="ibm_watsonx",
)
print(result.passed)
```

---

Google retrieves. Cedar authorizes. IBM federates. None of them proves.
Build the proofs.

## 10. Related: OpenAI Frontier vs Google vs Microsoft

A parallel three-way comparison covers the **business accessibility** axis:

- **OpenAI Frontier** — Business Context + "AI co-worker" governance (layers 1 and 2)
- **Google Knowledge Catalog** — open-standards retrieval (RDF/JSON-LD)
- **Microsoft Fabric IQ** — formal domain modelling inside DirectLake

All three share the same gap: no OWL, no SHACL. See
`docs/openai_frontier_vs_google_vs_microsoft.md` for the full analysis and
`OpenAIFrontierAdapter` code example.
