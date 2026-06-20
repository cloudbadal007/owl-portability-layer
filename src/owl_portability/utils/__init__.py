"""Utilities for RDF construction and SHACL reporting."""

from owl_portability.utils.rdf_builder import dict_to_entity_graph
from owl_portability.utils.shacl_reporter import violations_from_report

__all__ = ["dict_to_entity_graph", "violations_from_report"]
