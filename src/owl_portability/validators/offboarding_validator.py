"""Cross-Platform Offboarding Validator — enforces the employee offboarding semantic contract across
ServiceNow (HR + IT), Microsoft (identity), and Salesforce (Finance).
Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import uuid4

import pyshacl
from rdflib import Graph, Literal, Namespace, RDF
from rdflib.namespace import XSD

OFF = Namespace("http://enterprise.org/offboarding#")


@dataclass
class OffboardingEvent:
    """Represents one employee offboarding event across domains."""

    employee_id: str
    hr_status: str
    it_status: str
    finance_status: str
    ad_revoked: bool
    completion_certified: bool = False
    termination_date: Optional[str] = None
    violations: list[str] = field(default_factory=list)
    severity: str = "none"  # "none" | "warning" | "critical"


class CrossPlatformOffboardingValidator:
    """Validate employee offboarding events with OWL + SHACL guards."""

    def __init__(self, ontology_path: str) -> None:
        """Load combined OWL+SHACL ontology from Turtle file.

        Args:
            ontology_path: Path to ontology file containing both OWL and SHACL.
        """
        self.ontology = Graph()
        self.ontology.parse(Path(ontology_path).as_posix(), format="turtle")
        self.shacl_graph = self.ontology

    def validate_offboarding(self, event: OffboardingEvent) -> tuple[bool, list[str]]:
        """Validate one offboarding event and annotate severity.

        Args:
            event: Event payload to validate.

        Returns:
            Tuple of (conforms, violations).
        """
        event_graph = self._build_event_rdf(event)
        data_graph = Graph()
        data_graph += self.ontology
        data_graph += event_graph
        conforms, report_graph, report_text = pyshacl.validate(
            data_graph,
            shacl_graph=self.shacl_graph,
            ont_graph=self.ontology,
            inference="rdfs",
            abort_on_first=False,
            allow_infos=True,
            allow_warnings=True,
        )
        violations = self._extract_violations(report_text, report_graph.serialize(format="turtle"))
        if any("🚨" in message for message in violations):
            event.severity = "critical"
        elif any("⚠️" in message for message in violations):
            event.severity = "warning"
        else:
            event.severity = "none"
        event.violations = violations
        return bool(conforms), violations

    def _build_event_rdf(self, event: OffboardingEvent) -> Graph:
        """Build RDF graph for an offboarding event.

        Args:
            event: Event to encode as RDF triples.

        Returns:
            Graph containing typed triples for the event.
        """
        graph = Graph()
        graph.bind("off", OFF)
        subject = OFF[f"offboarding-{event.employee_id}-{uuid4().hex[:8]}"]
        graph.add((subject, RDF.type, OFF.EmployeeOffboarding))
        graph.add((subject, OFF.employeeId, Literal(event.employee_id, datatype=XSD.string)))
        graph.add((subject, OFF.hasHRStatus, Literal(event.hr_status, datatype=XSD.string)))
        graph.add((subject, OFF.hasITStatus, Literal(event.it_status, datatype=XSD.string)))
        graph.add(
            (subject, OFF.hasFinanceStatus, Literal(event.finance_status, datatype=XSD.string))
        )
        graph.add(
            (
                subject,
                OFF.activeDirectoryRevoked,
                Literal(event.ad_revoked, datatype=XSD.boolean),
            )
        )
        graph.add(
            (
                subject,
                OFF.completionCertified,
                Literal(event.completion_certified, datatype=XSD.boolean),
            )
        )
        if event.termination_date:
            graph.add(
                (
                    subject,
                    OFF.terminationDate,
                    Literal(event.termination_date, datatype=XSD.date),
                )
            )
        return graph

    def generate_report(self, events: list[OffboardingEvent]) -> str:
        """Generate plain text summary report across events.

        Args:
            events: Events to summarize.

        Returns:
            Human-readable report text.
        """
        total = len(events)
        critical = sum(1 for event in events if event.severity == "critical")
        warning = sum(1 for event in events if event.severity == "warning")
        flagged = critical + warning
        clean = total - flagged

        lines = [
            "CROSS-PLATFORM OFFBOARDING REPORT",
            f"Total events: {total}",
            f"Clean: {clean}",
            f"Flagged: {flagged}",
            f"Critical: {critical}",
            "",
        ]
        for event in events:
            if event.severity == "none":
                continue
            lines.append(f"Employee: {event.employee_id}")
            lines.append(f"Severity: {event.severity}")
            for violation in event.violations:
                lines.append(f"- {violation}")
            lines.append("")
        lines.append(
            "Cross-platform offboarding report. Review all flagged events before certifying completion."
        )
        return "\n".join(lines)

    def _extract_violations(self, report_text: str, fallback_text: str) -> list[str]:
        """Extract violation messages from SHACL report text.

        Args:
            report_text: Main textual pyshacl report.
            fallback_text: Serialized report graph text for fallback scan.

        Returns:
            List of unique warning/critical messages.
        """
        violations: list[str] = []
        for source_text in (report_text, fallback_text):
            for line in source_text.splitlines():
                candidate = line.strip()
                if "🚨" in candidate or "⚠️" in candidate:
                    violations.append(candidate)
        deduped: list[str] = []
        for violation in violations:
            if violation not in deduped:
                deduped.append(violation)
        return deduped
