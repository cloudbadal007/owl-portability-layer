"""Tests for the KYC extraction adapter pipeline.

Part of the enterprise ontology governance stack.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.kyc_extraction.confluence_chunker import ConfluenceChunker
from adapters.kyc_extraction.merge_deduplicator import MergeDeduplicator
from adapters.kyc_extraction.oracle_ddl_parser import OracleDDLParser
from adapters.kyc_extraction.slack_filter import SlackFilter
from adapters.kyc_extraction.validator import OntologyValidator

KYC_DIR = ROOT / "adapters" / "kyc_extraction"
SAMPLE_ONTOLOGY = KYC_DIR / "kyc_sample.ttl"
SAMPLE_DATA = KYC_DIR / "sample_data.ttl"

SAMPLE_DDL = """
CREATE TABLE customers (
  customer_id NUMBER(10) NOT NULL,
  legal_name VARCHAR2(200) NOT NULL,
  risk_rating VARCHAR2(20) CHECK (risk_rating IN ('LOW', 'MEDIUM', 'HIGH')),
  CONSTRAINT pk_customers PRIMARY KEY (customer_id)
);

CREATE TABLE accounts (
  account_id NUMBER(10) PRIMARY KEY,
  customer_id NUMBER(10) NOT NULL REFERENCES customers(customer_id),
  balance NUMBER(15,2) DEFAULT 0
);
"""


class _MockLLM:
    """Deterministic LLM stub for pipeline tests."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> Any:
        self.prompts.append(prompt)
        return self._response


@pytest.fixture
def ddl_parser() -> OracleDDLParser:
    return OracleDDLParser()


@pytest.fixture
def merge_deduplicator() -> MergeDeduplicator:
    return MergeDeduplicator()


@pytest.fixture
def ontology_validator() -> OntologyValidator:
    return OntologyValidator()


def test_oracle_parse_ddl_extracts_tables_and_constraints(
    ddl_parser: OracleDDLParser,
) -> None:
    """OracleDDLParser extracts tables, CHECK constraints, and foreign keys."""
    tables = ddl_parser.parse_ddl(SAMPLE_DDL)
    assert len(tables) == 2
    customers = next(table for table in tables if table["table_name"] == "customers")
    assert any(column["name"] == "risk_rating" and column.get("check") for column in customers["columns"])
    accounts = next(table for table in tables if table["table_name"] == "accounts")
    assert accounts["foreign_keys"][0]["to_table"] == "customers"


def test_oracle_to_owl_prompt_requires_single_table(ddl_parser: OracleDDLParser) -> None:
    """to_owl_prompt enforces one table per chunk."""
    tables = ddl_parser.parse_ddl(SAMPLE_DDL)
    prompt = ddl_parser.to_owl_prompt([tables[0]])
    assert "ASSUMPTION" in prompt
    assert "customers" in prompt
    with pytest.raises(ValueError):
        ddl_parser.to_owl_prompt(tables)


def test_oracle_extract_writes_turtle_with_mock_llm(
    ddl_parser: OracleDDLParser,
    tmp_path: Path,
) -> None:
    """extract() writes merged Turtle using a mock LLM response per table."""
    ddl_file = tmp_path / "schema.sql"
    output_file = tmp_path / "kyc_draft.ttl"
    ddl_file.write_text(SAMPLE_DDL, encoding="utf-8")
    llm = _MockLLM("@prefix kyc: <https://example-bank.com/ontology/kyc#> .\nkyc:Customer a owl:Class .")
    ddl_parser.extract(str(ddl_file), llm, str(output_file))
    content = output_file.read_text(encoding="utf-8")
    assert "kyc:Customer" in content
    assert len(llm.prompts) == 2


def test_confluence_chunk_by_section_and_prompt() -> None:
    """ConfluenceChunker splits numbered sections and builds OWL prompts."""
    chunker = ConfluenceChunker.__new__(ConfluenceChunker)
    page = {
        "title": "KYC Policy",
        "body": "Preamble\n3.1 Customer identification\nRequire valid ID.\n3.2 Screening\nRun sanctions.",
        "version": 2,
        "url": "https://example.atlassian.net/wiki/spaces/KYC/pages/1",
    }
    chunks = chunker.chunk_by_section(page)
    assert len(chunks) >= 2
    assert chunks[0]["confidence"] == 0.70
    prompt = chunker.to_owl_prompt(chunks[0])
    assert "valid Turtle" in prompt
    assert "SOURCE:" in prompt
    assert "ASSUMPTION" in prompt


def test_slack_filter_excludes_noise_and_builds_prompt() -> None:
    """SlackFilter excludes bots and short messages; prompt omits superseded ts."""
    slack = SlackFilter.__new__(SlackFilter)
    assert slack._should_exclude({"bot_id": "B1", "text": "x" * 40})
    assert slack._should_exclude({"subtype": "file_share", "text": "x" * 40})
    assert slack._should_exclude({"text": "short"})
    assert not slack._should_exclude({"text": "Compliance policy update for EDD workflow"})

    messages = [
        {"text": "Old PEP review rule applies annually", "user": "U1", "ts": "1.0", "thread_ts": "1.0"},
        {"text": "New PEP review rule applies every 12 months", "user": "U2", "ts": "2.0", "thread_ts": "2.0"},
    ]
    conflicts = [
        {
            "earlier_ts": "1.0",
            "later_ts": "2.0",
            "description": "PEP review interval changed",
            "authoritative_ts": "2.0",
        }
    ]
    prompt = slack.to_owl_prompt(messages, conflicts)
    assert "confidence 0.40" in prompt
    assert "ts=2.0" in prompt
    assert "ts=1.0" not in prompt.split("Active messages", 1)[1]


def test_slack_detect_conflicts_parses_json() -> None:
    """detect_conflicts parses a JSON conflict array from the LLM."""
    slack = SlackFilter.__new__(SlackFilter)
    messages = [
        {"text": "Old rule applies", "user": "U1", "ts": "1.0", "thread_ts": "1.0"},
        {"text": "New rule supersedes old rule", "user": "U2", "ts": "2.0", "thread_ts": "2.0"},
    ]
    payload = json.dumps(
        [
            {
                "earlier_ts": "1.0",
                "later_ts": "2.0",
                "description": "Rule changed",
                "authoritative_ts": "2.0",
            }
        ]
    )
    llm = _MockLLM(payload)
    conflicts = slack.detect_conflicts(messages, llm)
    assert len(conflicts) == 1
    assert conflicts[0]["authoritative_ts"] == "2.0"


def test_merge_extract_class_names_and_substitutions(merge_deduplicator: MergeDeduplicator) -> None:
    """MergeDeduplicator extracts class names and rewrites synonyms outside comments."""
    turtle = """
@prefix kyc: <https://example-bank.com/ontology/kyc#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
kyc:KYC_CUSTOMER a owl:Class .
# <!-- ASSUMPTION: from DDL -->
kyc:KYC_CUSTOMER kyc:relatesTo kyc:account_holder .
kyc:account_holder a owl:Class .
"""
    classes = merge_deduplicator.extract_class_names(turtle)
    assert classes == {"KYC_CUSTOMER", "account_holder"}
    clusters = [
        {
            "canonical": "Customer",
            "synonyms": ["KYC_CUSTOMER", "account_holder"],
            "confidence": 0.9,
            "note": "same concept",
        }
    ]
    merged = merge_deduplicator.apply_substitutions(turtle, clusters)
    assert "kyc:Customer" in merged
    assert "<!-- ASSUMPTION: from DDL -->" in merged


def test_merge_pipeline_with_mock_llm(
    merge_deduplicator: MergeDeduplicator,
    tmp_path: Path,
) -> None:
    """merge() clusters classes and writes deduplicated Turtle output."""
    input_file = tmp_path / "draft.ttl"
    output_file = tmp_path / "merged.ttl"
    input_file.write_text(
        "@prefix kyc: <https://example-bank.com/ontology/kyc#> .\n"
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "kyc:KYC_CUSTOMER a owl:Class .\n",
        encoding="utf-8",
    )
    llm = _MockLLM(
        json.dumps(
            [
                {
                    "canonical": "Customer",
                    "synonyms": ["KYC_CUSTOMER"],
                    "confidence": 0.95,
                    "note": "DDL alias",
                }
            ]
        )
    )
    merge_deduplicator.merge([str(input_file)], llm, str(output_file))
    assert "kyc:Customer" in output_file.read_text(encoding="utf-8")


def test_kyc_sample_ttl_is_valid_rdf() -> None:
    """kyc_sample.ttl parses as valid RDF."""
    graph = Graph()
    graph.parse(SAMPLE_ONTOLOGY.as_posix(), format="turtle")
    assert len(graph) > 0


def test_validator_count_assumptions_and_report(ontology_validator: OntologyValidator) -> None:
    """OntologyValidator counts assumptions and formats a review report."""
    assumption_count = ontology_validator.count_assumptions(str(SAMPLE_ONTOLOGY))
    assert assumption_count == 1
    report = ontology_validator.generate_review_report(str(SAMPLE_ONTOLOGY), [], [])
    assert "SUMMARY" in report
    assert "ASSUMPTIONS FOR REVIEW" in report
    assert "Estimated domain expert review time: 0.1 hours" in report


def test_validator_derives_shacl_shapes(ontology_validator: OntologyValidator) -> None:
    """SHACL shapes are derived from OWL domain and range axioms."""
    ontology_graph = Graph()
    ontology_graph.parse(SAMPLE_ONTOLOGY.as_posix(), format="turtle")
    shacl_graph = ontology_validator._derive_shacl_from_owl(ontology_graph)  # noqa: SLF001
    assert len(shacl_graph) > 0


def test_validator_shacl_runs_on_sample_data(ontology_validator: OntologyValidator) -> None:
    """validate_shacl runs against sample instance data without raising."""
    violations = ontology_validator.validate_shacl(str(SAMPLE_ONTOLOGY), str(SAMPLE_DATA))
    assert isinstance(violations, list)


@pytest.mark.skipif(
    importlib.util.find_spec("owlready2") is None,
    reason="owlready2 not installed",
)
def test_validator_owl_consistency_optional(ontology_validator: OntologyValidator) -> None:
    """OWL consistency check runs when owlready2 and Pellet are available."""
    errors = ontology_validator.validate_owl_consistency(str(SAMPLE_ONTOLOGY))
    assert isinstance(errors, list)
