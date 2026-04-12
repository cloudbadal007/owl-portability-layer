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

## Dict shape

Payloads should use ontology **local names** as keys. Nested resources use a dict with `"@type": "ClassName"` and property keys matching `proc:*` in Turtle.

## Simulation mode

Demos and tests must run without credentials. Use httpx against a stub URL, catch `HTTPError`, log, and return success where appropriate—match the pattern in `palantir.py` and `fabric_iq.py`.

## Testing

Add tests under `tests/test_adapters.py` (or a new module) that only assert your adapter does not raise and returns expected booleans in simulation mode.
