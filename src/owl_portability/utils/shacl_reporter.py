"""Extract human-readable SHACL violation messages from validation reports."""

from __future__ import annotations

from rdflib import Graph
from rdflib.namespace import RDF, SH


def violations_from_report(report_graph: Graph | None, report_text: str | None) -> list[str]:
    """Parse pyshacl's validation report graph and text into a deduplicated message list.

    Args:
        report_graph: RDF graph returned by ``pyshacl.validate`` (may be empty).
        report_text: Plain-text report from pyshacl, used as fallback.

    Returns:
        Ordered list of violation strings suitable for logs and APIs.
    """
    messages: list[str] = []
    if report_graph is not None:
        for result in report_graph.subjects(RDF.type, SH.ValidationResult):
            for msg in report_graph.objects(result, SH.resultMessage):
                text = str(msg).strip()
                if text and text not in messages:
                    messages.append(text)
            for detail in report_graph.objects(result, SH.detail):
                for nested in report_graph.objects(detail, SH.resultMessage):
                    t = str(nested).strip()
                    if t and t not in messages:
                        messages.append(t)
    if not messages and report_text:
        stripped = report_text.strip()
        if stripped:
            messages.append(stripped)
    return messages
