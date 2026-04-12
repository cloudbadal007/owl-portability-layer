"""Build RDF graphs from plain dict payloads for SHACL validation."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

logger = logging.getLogger(__name__)

PROC = Namespace("http://enterprise.org/procurement#")


def _entity_uri(entity_class: str, entity_id: str | None) -> URIRef:
    slug = entity_id or f"entity-{uuid.uuid4().hex[:12]}"
    return URIRef(f"http://enterprise.org/procurement/instance/{entity_class}/{slug}")


def dict_to_entity_graph(
    data: dict[str, Any],
    entity_class: str,
    *,
    ontology_graph: Graph | None = None,
) -> Graph:
    """Map a dict payload to an RDF graph with a typed root resource.

    Keys are typically local names matching ontology properties (``amountUSD``,
    ``hasHoldStatus``, etc.). Object keys pointing to nested dicts become
    linked resources (blank or named nodes) with their own ``rdf:type``.

    Args:
        data: Payload keyed by property local names.
        entity_class: OWL class name for the root node (``PaymentEvent``, ``Contract``, ...).
        ontology_graph: Unused reserved for future IRI validation; keeps API stable.

    Returns:
        A new ``rdflib.Graph`` containing triples for the entity and nested nodes.

    Raises:
        ValueError: If a nested structure cannot be interpreted as RDF.
    """
    _ = ontology_graph  # reserved — avoid coupling validation to OWL reasoning here
    g = Graph()
    root_id = data.get("@id") or data.get("id")
    if isinstance(root_id, str):
        root = URIRef(root_id)
    else:
        root = _entity_uri(entity_class, str(root_id) if root_id is not None else None)
    g.add((root, RDF.type, PROC[entity_class]))

    for key, value in data.items():
        if key in ("@id", "id"):
            continue
        if key.startswith("_"):
            continue
        prop = PROC[key]
        if isinstance(value, dict):
            nested_type = value.get("@type") or value.get("type") or "Resource"
            node: URIRef | BNode
            if isinstance(nested_type, str) and nested_type != "Resource":
                nid = value.get("@id") or value.get("id")
                if isinstance(nid, str):
                    node = URIRef(nid)
                else:
                    node = BNode()
                g.add((node, RDF.type, PROC[nested_type]))
            else:
                node = BNode()
            for nk, nv in value.items():
                if nk in ("@id", "id", "@type", "type"):
                    continue
                sub_prop = PROC[nk]
                _add_literal_or_link(g, node, sub_prop, nv, property_name=nk)
            g.add((root, prop, node))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested_type = item.get("@type") or item.get("type") or "Resource"
                    node = BNode()
                    if isinstance(nested_type, str):
                        g.add((node, RDF.type, PROC[nested_type]))
                    for nk, nv in item.items():
                        if nk in ("@id", "id", "@type", "type"):
                            continue
                        _add_literal_or_link(g, node, PROC[nk], nv, property_name=nk)
                    g.add((root, prop, node))
                else:
                    _add_literal_or_link(g, root, prop, item, property_name=key)
        else:
            _add_literal_or_link(g, root, prop, value, property_name=key)

    return g


def _add_literal_or_link(
    g: Graph,
    subject: URIRef | BNode,
    predicate: Any,
    value: Any,
    *,
    property_name: str | None = None,
) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        g.add((subject, predicate, Literal(value, datatype=XSD.boolean)))
    elif isinstance(value, int):
        if property_name in ("amountUSD", "contractValue"):
            g.add((subject, predicate, Literal(Decimal(value), datatype=XSD.decimal)))
        else:
            g.add((subject, predicate, Literal(value, datatype=XSD.integer)))
    elif isinstance(value, float):
        g.add((subject, predicate, Literal(Decimal(str(value)), datatype=XSD.decimal)))
    elif isinstance(value, Decimal):
        g.add((subject, predicate, Literal(value, datatype=XSD.decimal)))
    elif isinstance(value, str):
        if value.startswith("http://") or value.startswith("https://"):
            g.add((subject, predicate, URIRef(value)))
        else:
            g.add((subject, predicate, Literal(value, datatype=XSD.string)))
    else:
        logger.debug("Coercing value to string for %s", predicate)
        g.add((subject, predicate, Literal(str(value), datatype=XSD.string)))
