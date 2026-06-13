# Adding a platform adapter

## Contract

Subclass `BaseAdapter` in `src/owl_portability/adapters/base.py` and implement:

- `platform_name` — short string for logs.
- `write(entity_data, entity_class) -> bool` — persist after validation.
- `read(entity_class, filters) -> list[dict]` — optional query for sync jobs.
- `health_check() -> bool` — connectivity or session check.

## Registration

```python
from owl_portability.layer import OWLPortabilityLayer
from mypkg import MyAdapter

layer = OWLPortabilityLayer("ontologies/procurement.ttl", "ontologies/procurement_shacl.ttl")
layer.register_adapter("my_platform", MyAdapter(...))
layer.validate_and_route(payload, "PaymentEvent", target_platform="my_platform")
```

## Two-layer governance adapters

When your platform ships its own governance (access control, Business Context,
runtime policy), add a `validate_*` method that:

1. **Short-circuits** on platform denial — do not run SHACL if the platform already blocked the action.
2. **Runs SHACL** when the platform permits — catch formal constraints the platform cannot express.
3. **Sets `safe_to_execute`** with AND logic — both layers must pass.

Reference implementations:

| Pattern | Adapter | Validate method |
|---|---|---|
| Business Context + SHACL | `OpenAIFrontierAdapter` | `validate_action()` |
| Cedar + SHACL | `AgentCoreSemanticAdapter` | `validate_tool_call()` |
| Runtime policy + SHACL | `IBMWatsonxContextAdapter` | `validate_with_shacl()` |
| Semantic grounding + SHACL | `DataverseSemanticAdapter` | `validate_dataverse_action()` |

`OpenAIFrontierAdapter` is the best starting point for a new two-layer adapter:
see `src/owl_portability/adapters/openai_frontier.py` and
`tests/test_openai_frontier_adapter.py`.

## Dict shape

Payloads should use ontology **local names** as keys. Nested resources use a dict with `"@type": "ClassName"` and property keys matching `proc:*` in Turtle.

## Simulation mode

Demos and tests must run without credentials. Use httpx against a stub URL, catch `HTTPError`, log, and return success where appropriate—match the pattern in `palantir.py`, `fabric_iq.py`, and `openai_frontier.py`.

Default `simulation_mode=True` on all new adapters.

## Testing

Add tests under `tests/` following the Frontier adapter pattern:

```bash
pytest tests/test_openai_frontier_adapter.py -v   # unit tests
pytest tests/test_nine_platform_portability.py -v # cross-platform integration
pytest tests/test_adapters.py -v                  # simulation smoke tests
```

Each adapter test file should cover:

- Platform denial short-circuits SHACL
- Platform permit + SHACL block (formal constraint gap)
- Both layers pass
- Vocabulary mapping (platform names → OWL classes)
- `safe_to_execute` AND logic
- `write` / `read` / `health_check` in simulation mode
- `platform_name` stability

Add a smoke test to `tests/test_adapters.py` for quick CI coverage.
