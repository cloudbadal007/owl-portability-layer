"""Migration readiness audit: Palantir object types vs OWL coverage."""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import OWL, RDF

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PROC = "http://enterprise.org/procurement#"


def load_ontology_classes(ttl_path: Path) -> set[str]:
    """Collect local names of declared OWL classes."""
    g = Graph()
    g.parse(ttl_path.as_posix(), format="turtle")
    classes: set[str] = set()
    for s, _, _ in g.triples((None, RDF.type, OWL.Class)):
        if str(s).startswith(PROC):
            classes.add(str(s).split("#")[-1])
    return classes


def audit(object_types: list[dict[str, str]]) -> None:
    """Print GREEN/AMBER/RED lines per simulated Palantir object type."""
    ttl = ROOT / "ontologies" / "procurement.ttl"
    owl_classes = load_ontology_classes(ttl)
    palantir_specific = {"ActionType", "OsdkFunction", "WorkshopModule"}

    print("Migration readiness (simulated inputs)\n")
    for row in object_types:
        name = row["name"]
        flags = row.get("flags", "")
        if name in palantir_specific or "ACTION" in flags or "OSDK" in flags:
            status = "RED"
            reason = "Relies on Palantir-specific constructs; no direct OWL projection."
        elif name in owl_classes:
            status = "GREEN"
            reason = "Clean OWL class match in procurement.ttl."
        else:
            status = "AMBER"
            reason = "Needs mapping or extension in the shared ontology."
        print(f"[{status}] {name}: {reason}")


def main() -> None:
    palantir_object_types = [
        {"name": "PaymentEvent", "flags": ""},
        {"name": "Vendor", "flags": ""},
        {"name": "LegacySpendAction", "flags": "ACTION"},
        {"name": "OsdkFunction", "flags": "OSDK"},
        {"name": "MysteryObject", "flags": ""},
    ]
    audit(palantir_object_types)


if __name__ == "__main__":
    main()
