# Migration guide

Use this layer when moving ontology-heavy workloads between Palantir Foundry, Microsoft Fabric IQ, or agent-first stacks (MCP).

## Before migration

1. **Inventory object types** (Foundry) or **IQ entity kinds** (Fabric) and list them alongside OWL class names in `procurement.ttl` (or your domain ontology).
2. **Run SHACL on sample exports**: Convert a batch of records to the dict shape expected by `dict_to_entity_graph` and run `OWLPortabilityLayer.validate_only`. Fix data or extend shapes until green.
3. **Flag vendor-only features**: Action Types, bespoke OSDK functions, or Workshop-only logic rarely map 1:1 to OWL. Track those as RED in your readiness report (see `demo_migration_check.py`).

## During migration

- Keep **one** canonical ontology + SHACL in Git; adapters are thin translation layers.
- Use **validate_only** in CI for both source and target shaped payloads before cutover.
- Prefer **MCPAdapter** for greenfield agent paths so you are not blocked on either vendor.

## After migration

- Delete or stub the old vendor adapter when the source is retired—the rest of the repo stays unchanged.
- Re-run the full pytest suite and your migration audit script on a schedule to catch schema drift.
