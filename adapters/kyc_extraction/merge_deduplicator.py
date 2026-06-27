"""Merge candidate concepts from all sources into a canonical vocabulary."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Protocol

_CLASS_NAME_RE = re.compile(r":(\w+)\s+a\s+owl:Class")
_COMMENT_BLOCK_RE = re.compile(r"(<!--.*?-->)", re.DOTALL)


class LLMClient(Protocol):
    """Minimal interface for LangChain-style chat models."""

    def invoke(self, prompt: str) -> Any:
        """Send a prompt and return a response object with extractable text."""


class MergeDeduplicator:
    """Cluster synonymous OWL class names and merge Turtle sources."""

    def load_candidates(self, turtle_paths: list[str]) -> list[str]:
        """Read Turtle candidate files from disk.

        Args:
            turtle_paths: Paths to Turtle files produced by upstream extractors.

        Returns:
            Raw Turtle document strings in the same order as ``turtle_paths``.
        """
        return [Path(path).read_text(encoding="utf-8") for path in turtle_paths]

    def extract_class_names(self, turtle_content: str) -> set[str]:
        """Extract proposed OWL class local names from Turtle text.

        Args:
            turtle_content: Turtle ontology or candidate fragment.

        Returns:
            Set of class local names declared with ``a owl:Class``.
        """
        return set(_CLASS_NAME_RE.findall(turtle_content))

    def build_merge_prompt(self, all_classes: set[str]) -> str:
        """Build an LLM prompt to cluster synonymous class names.

        Args:
            all_classes: Union of class names discovered across all inputs.

        Returns:
            Prompt requesting JSON cluster objects with ``canonical``,
            ``synonyms``, ``confidence``, and ``note`` keys.
        """
        class_list = sorted(all_classes)
        example = {
            "canonical": "Customer",
            "synonyms": ["KYC_CUSTOMER", "account_holder", "the client"],
            "confidence": 0.92,
            "note": "All refer to the onboarded banking customer",
        }
        return "\n".join(
            [
                "Cluster the proposed KYC ontology class names by real-world concept.",
                "Return ONLY a JSON list of objects.",
                "Each object must contain these keys:",
                "  canonical (str), synonyms (list[str]), confidence (float), note (str)",
                "Every input class name must appear exactly once: either as a canonical value",
                "or inside exactly one synonyms list.",
                "",
                "Example object:",
                json.dumps(example, indent=2),
                "",
                "Class names to cluster:",
                json.dumps(class_list, indent=2),
            ]
        )

    def apply_substitutions(self, merged_turtle: str, clusters: list[dict[str, Any]]) -> str:
        """Replace synonym class references with canonical names.

        Substitutions are applied outside HTML comment blocks so ``ASSUMPTION``
        and ``SOURCE`` annotations are preserved verbatim.

        Args:
            merged_turtle: Combined Turtle text before deduplication.
            clusters: Cluster dictionaries returned by the LLM.

        Returns:
            Turtle text with synonym references rewritten to canonical names.
        """
        def substitute_segment(segment: str) -> str:
            updated = segment
            for cluster in clusters:
                canonical = str(cluster["canonical"])
                canonical_local = canonical.split(":", 1)[-1]
                canonical_ref = canonical if ":" in canonical else f"kyc:{canonical_local}"

                for synonym in cluster.get("synonyms", []):
                    synonym_local = str(synonym).split(":", 1)[-1]
                    if synonym_local == canonical_local:
                        continue
                    updated = re.sub(
                        rf"\b(\w+:){re.escape(synonym_local)}\b",
                        canonical_ref,
                        updated,
                    )
                    updated = re.sub(
                        rf"\b{re.escape(synonym_local)}\b",
                        canonical_local,
                        updated,
                    )
            return updated

        parts = _COMMENT_BLOCK_RE.split(merged_turtle)
        for index in range(0, len(parts), 2):
            parts[index] = substitute_segment(parts[index])
        return "".join(parts)

    def merge(self, turtle_paths: list[str], llm: LLMClient, output_path: str) -> None:
        """Run the full merge-and-deduplicate pipeline.

        Args:
            turtle_paths: Input Turtle files to merge.
            llm: Chat model implementing ``invoke(prompt)``.
            output_path: Destination path for merged Turtle output.
        """
        documents = self.load_candidates(turtle_paths)
        merged_turtle = "\n\n".join(documents)

        all_classes: set[str] = set()
        for document in documents:
            all_classes.update(self.extract_class_names(document))

        class_count = len(all_classes)
        if class_count == 0:
            Path(output_path).write_text(
                "# No owl:Class declarations found in input Turtle files.\n",
                encoding="utf-8",
            )
            print("Merged 0 classes into 0 canonical concepts")
            return

        response = llm.invoke(self.build_merge_prompt(all_classes))
        clusters = self._parse_cluster_response(response)
        deduplicated = self.apply_substitutions(merged_turtle, clusters)

        header = [
            "# Merged KYC ontology candidates",
            f"# Source files: {', '.join(turtle_paths)}",
            "",
        ]
        Path(output_path).write_text(
            "\n".join(header) + deduplicated.rstrip() + "\n",
            encoding="utf-8",
        )
        print(f"Merged {class_count} classes into {len(clusters)} canonical concepts")

    def _parse_cluster_response(self, response: Any) -> list[dict[str, Any]]:
        """Parse the JSON cluster list from an LLM response."""
        text = self._response_to_text(response)
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()

        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return []

        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed, list):
            return []

        clusters: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            if "canonical" not in item or "synonyms" not in item:
                continue
            clusters.append(
                {
                    "canonical": str(item["canonical"]),
                    "synonyms": [str(synonym) for synonym in item["synonyms"]],
                    "confidence": float(item.get("confidence", 0.0)),
                    "note": str(item.get("note", "")),
                }
            )
        return clusters

    def _response_to_text(self, response: Any) -> str:
        """Normalize LangChain or plain-string LLM responses to text."""
        if isinstance(response, str):
            return response
        if hasattr(response, "content"):
            content = response.content
            return content if isinstance(content, str) else str(content)
        return str(response)


def _build_default_llm() -> LLMClient:
    """Construct the default Anthropic chat model from environment configuration."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise SystemExit(
            "langchain-anthropic is required for CLI merge. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    return ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


def main() -> None:
    """CLI entry point for Turtle merge and deduplication."""
    parser = argparse.ArgumentParser(
        description="Merge KYC Turtle candidates and deduplicate class names via LLM."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input Turtle files to merge",
    )
    parser.add_argument("--output", required=True, help="Output Turtle file path")
    args = parser.parse_args()

    MergeDeduplicator().merge(args.inputs, _build_default_llm(), args.output)


if __name__ == "__main__":
    main()
