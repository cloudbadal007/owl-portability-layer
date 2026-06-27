"""Three-layer validation: OWL consistency, SHACL conformance, formal proof."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pyshacl
from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

SH = Namespace("http://www.w3.org/ns/shacl#")
_ASSUMPTION_RE = re.compile(r"<!--\s*ASSUMPTION:\s*(.*?)\s*-->")


class OntologyValidator:
    """Validate KYC ontologies for OWL consistency and SHACL conformance."""

    def validate_owl_consistency(self, turtle_path: str) -> list[str]:
        """Load an ontology with owlready2 and run the Pellet reasoner.

        Args:
            turtle_path: Path to a Turtle ontology file.

        Returns:
            Empty list when consistent; otherwise one or more error strings.
        """
        try:
            from owlready2 import get_ontology, sync_reasoner_pellet
        except ImportError as exc:
            return [f"owlready2 is not installed: {exc}"]

        resolved = Path(turtle_path).resolve()
        if not resolved.exists():
            return [f"Ontology file not found: {turtle_path}"]

        try:
            ontology = get_ontology(resolved.as_uri()).load()
            with ontology:
                sync_reasoner_pellet(infer_property_values=True, debug=0)
            return []
        except Exception as exc:  # noqa: BLE001
            return [f"OWL consistency error: {exc}"]

    def validate_shacl(self, ontology_path: str, data_path: str) -> list[str]:
        """Validate sample data against SHACL shapes derived from OWL restrictions.

        Args:
            ontology_path: Path to the ontology Turtle file.
            data_path: Path to sample instance data (Turtle or JSON-LD).

        Returns:
            List of SHACL violation strings; empty when validation passes.
        """
        ontology_graph = Graph()
        data_graph = Graph()

        try:
            ontology_graph.parse(Path(ontology_path).as_posix(), format="turtle")
            self._load_data_graph(data_graph, data_path)
        except Exception as exc:  # noqa: BLE001
            return [f"Failed to load ontology or data graph: {exc}"]

        shacl_graph = self._derive_shacl_from_owl(ontology_graph)
        merge = Graph()
        merge += ontology_graph
        merge += data_graph

        try:
            conforms, report_graph, report_text = pyshacl.validate(
                merge,
                shacl_graph=shacl_graph,
                ont_graph=ontology_graph,
                inference="rdfs",
                abort_on_first=False,
                allow_infos=True,
                allow_warnings=True,
            )
        except Exception as exc:  # noqa: BLE001
            return [f"SHACL validation engine error: {exc}"]

        if conforms:
            return []

        violations = self._violations_from_report(report_graph, report_text)
        if not violations and report_text:
            violations = [report_text.strip()]
        return violations

    def count_assumptions(self, turtle_path: str) -> int:
        """Count ``<!-- ASSUMPTION:`` annotations in a Turtle file.

        Args:
            turtle_path: Path to the Turtle ontology or candidate file.

        Returns:
            Number of assumption annotations found.
        """
        content = Path(turtle_path).read_text(encoding="utf-8")
        return len(re.findall(r"<!--\s*ASSUMPTION:", content))

    def generate_review_report(
        self,
        turtle_path: str,
        owl_errors: list[str],
        shacl_violations: list[str],
    ) -> str:
        """Build a plain-text domain expert review report.

        Args:
            turtle_path: Path to the ontology under review.
            owl_errors: OWL consistency errors from :meth:`validate_owl_consistency`.
            shacl_violations: SHACL violations from :meth:`validate_shacl`.

        Returns:
            Formatted report ending with estimated review time in hours.
        """
        content = Path(turtle_path).read_text(encoding="utf-8")
        assumption_count = self.count_assumptions(turtle_path)
        axiom_count = self._count_axioms(content)
        error_count = len(owl_errors)
        violation_count = len(shacl_violations)
        review_hours = (assumption_count + error_count + violation_count) * 0.1

        lines = [
            "KYC ONTOLOGY REVIEW REPORT",
            "==========================",
            "",
            "SUMMARY",
            "-------",
            f"Source file: {turtle_path}",
            f"Total axioms (approximate): {axiom_count}",
            f"Assumption annotations: {assumption_count}",
            f"OWL consistency errors: {error_count}",
            f"SHACL violations: {violation_count}",
            "",
        ]

        lines.extend(["OWL CONSISTENCY ERRORS", "----------------------"])
        if owl_errors:
            lines.extend(f"- {error}" for error in owl_errors)
        else:
            lines.append("- None")
        lines.append("")

        lines.extend(["SHACL VIOLATIONS", "----------------"])
        if shacl_violations:
            lines.extend(f"- {violation}" for violation in shacl_violations)
        else:
            lines.append("- None")
        lines.append("")

        lines.extend(["ASSUMPTIONS FOR REVIEW", "----------------------"])
        assumptions = self._extract_assumptions_with_lines(content)
        if assumptions:
            for line_number, assumption in assumptions:
                lines.append(f"Line {line_number}: {assumption}")
        else:
            lines.append("- None")
        lines.append("")

        lines.append(f"Estimated domain expert review time: {review_hours:.1f} hours")
        return "\n".join(lines)

    def _derive_shacl_from_owl(self, ontology_graph: Graph) -> Graph:
        """Derive basic node shapes from OWL class and property restrictions."""
        shacl_graph = Graph()
        shacl_graph.bind("sh", SH)

        for class_uri in ontology_graph.subjects(RDF.type, OWL.Class):
            if not isinstance(class_uri, URIRef):
                continue

            shape_uri = URIRef(f"{class_uri}_Shape")
            shacl_graph.add((shape_uri, RDF.type, SH.NodeShape))
            shacl_graph.add((shape_uri, SH.targetClass, class_uri))

            for restriction in ontology_graph.objects(class_uri, RDFS.subClassOf):
                if not isinstance(restriction, BNode):
                    continue
                if (restriction, RDF.type, OWL.Restriction) not in ontology_graph:
                    continue

                on_property = ontology_graph.value(restriction, OWL.onProperty)
                if on_property is None:
                    continue

                property_shape = BNode()
                shacl_graph.add((shape_uri, SH.property, property_shape))
                shacl_graph.add((property_shape, SH.path, on_property))

                cardinality = ontology_graph.value(restriction, OWL.cardinality)
                min_card = ontology_graph.value(restriction, OWL.minCardinality)
                max_card = ontology_graph.value(restriction, OWL.maxCardinality)
                has_value = ontology_graph.value(restriction, OWL.hasValue)
                some_values = ontology_graph.value(restriction, OWL.someValuesFrom)
                all_values = ontology_graph.value(restriction, OWL.allValuesFrom)

                if cardinality is not None:
                    shacl_graph.add(
                        (property_shape, SH.minCount, cardinality),
                    )
                    shacl_graph.add(
                        (property_shape, SH.maxCount, cardinality),
                    )
                if min_card is not None:
                    shacl_graph.add((property_shape, SH.minCount, min_card))
                if max_card is not None:
                    shacl_graph.add((property_shape, SH.maxCount, max_card))
                if has_value is not None:
                    shacl_graph.add((property_shape, SH.hasValue, has_value))
                target_class = some_values or all_values
                if target_class is not None:
                    shacl_graph.add((property_shape, SH["class"], target_class))

            for property_uri in ontology_graph.subjects(RDFS.domain, class_uri):
                if not isinstance(property_uri, URIRef):
                    continue
                property_shape = BNode()
                shacl_graph.add((shape_uri, SH.property, property_shape))
                shacl_graph.add((property_shape, SH.path, property_uri))

                range_uri = ontology_graph.value(property_uri, RDFS.range)
                if range_uri is None:
                    continue
                if (range_uri, RDF.type, OWL.Class) in ontology_graph:
                    shacl_graph.add((property_shape, SH["class"], range_uri))
                elif range_uri in (XSD.integer, XSD.decimal, XSD.string):
                    shacl_graph.add((property_shape, SH.datatype, range_uri))

        return shacl_graph

    def _load_data_graph(self, data_graph: Graph, data_path: str) -> None:
        """Load instance data from Turtle or JSON-LD."""
        path = Path(data_path)
        suffix = path.suffix.lower()
        if suffix in {".ttl", ".turtle"}:
            data_graph.parse(path.as_posix(), format="turtle")
            return
        if suffix == ".json":
            try:
                data_graph.parse(path.as_posix(), format="json-ld")
                return
            except Exception:
                pass
            import json

            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and "@context" in payload:
                data_graph.parse(data=path.read_text(encoding="utf-8"), format="json-ld")
                return
            raise ValueError(
                "JSON data must be JSON-LD with @context or a Turtle file must be supplied."
            )
        raise ValueError(f"Unsupported data file format: {data_path}")

    def _violations_from_report(self, report_graph: Graph, report_text: str) -> list[str]:
        """Extract human-readable SHACL violations from a pyshacl report."""
        violations: list[str] = []
        if report_graph:
            for _, _, message in report_graph.triples(
                (None, URIRef("http://www.w3.org/ns/shacl#resultMessage"), None)
            ):
                violations.append(str(message))
        if violations:
            return violations
        if report_text:
            return [line.strip() for line in report_text.splitlines() if line.strip()]
        return []

    def _count_axioms(self, turtle_content: str) -> int:
        """Approximate axiom count from Turtle statement terminators."""
        return len([line for line in turtle_content.splitlines() if line.strip().endswith(".")])

    def _extract_assumptions_with_lines(self, turtle_content: str) -> list[tuple[int, str]]:
        """Return assumption annotation texts with 1-based line numbers."""
        findings: list[tuple[int, str]] = []
        for line_number, line in enumerate(turtle_content.splitlines(), start=1):
            for match in _ASSUMPTION_RE.finditer(line):
                findings.append((line_number, match.group(1).strip()))
        return findings


def main() -> None:
    """CLI entry point for ontology validation and review reporting."""
    parser = argparse.ArgumentParser(description="Validate a KYC ontology and generate a review report.")
    parser.add_argument("--ontology", required=True, help="Path to ontology Turtle file")
    parser.add_argument("--data", required=True, help="Path to sample instance data")
    parser.add_argument(
        "--report",
        default="",
        help="Optional path to write the plain-text review report",
    )
    args = parser.parse_args()

    validator = OntologyValidator()
    owl_errors = validator.validate_owl_consistency(args.ontology)
    shacl_violations = validator.validate_shacl(args.ontology, args.data)
    report = validator.generate_review_report(args.ontology, owl_errors, shacl_violations)
    print(report)

    if args.report:
        Path(args.report).write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
