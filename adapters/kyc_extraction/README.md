# KYC Extraction Adapter

Companion code for the Medium article:
"I Asked an LLM to Build JPMorgan's Compliance Ontology. Here's What It Got Wrong."
[MEDIUM ARTICLE LINK — add when published]

This adapter extracts a KYC compliance ontology from five enterprise source 
systems — Oracle/SQL, Confluence, Slack, Salesforce, and MongoDB — using an 
LLM-assisted pipeline with structured ASSUMPTION annotations and three-layer 
validation.

## Files

- `oracle_ddl_parser.py` — Parses Oracle/PostgreSQL DDL and proposes OWL classes and properties
- `confluence_chunker.py` — Chunks Confluence policy pages by section and extracts axiom candidates
- `slack_filter.py` — Filters compliance team Slack messages and detects superseded rulings
- `merge_deduplicator.py` — Merges candidate concepts from all sources into a canonical vocabulary
- `validator.py` — Three-layer validation: OWL consistency, SHACL conformance, formal proof
- `kyc_sample.ttl` — Sample KYC ontology in OWL 2 Turtle format

## Usage

```bash
pip install -r requirements.txt
python oracle_ddl_parser.py --ddl path/to/schema.sql --output kyc_draft.ttl
python confluence_chunker.py --space KYC --output confluence_candidates.ttl
python slack_filter.py --channel kyc-compliance-ops --days 90 --output slack_candidates.ttl
python merge_deduplicator.py --inputs kyc_draft.ttl confluence_candidates.ttl slack_candidates.ttl --output kyc_merged.ttl
python validator.py --ontology kyc_merged.ttl --data sample_data.ttl
```

## Testing

From the repository root (offline, no API credentials):

```bash
pytest tests/test_kyc_extraction.py -v
```

`sample_data.ttl` provides instance data for SHACL validation against `kyc_sample.ttl`.

## Related adapters

- `adapters/ibm_watsonx/` — IBM watsonx portability adapter
- `adapters/palantir_foundry/` — Palantir Foundry portability adapter
- `adapters/grok_databricks/` — Grok on Databricks portability adapter
