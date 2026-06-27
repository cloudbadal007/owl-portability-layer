"""Chunk Confluence policy pages and extract axiom candidates."""

from __future__ import annotations

import argparse
import os
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol

_SECTION_SPLIT_RE = re.compile(r"\n(?=\d+\.\d+\s)")
_SECTION_HEADING_RE = re.compile(r"^(\d+\.\d+\s+[^\n]+)")


class LLMClient(Protocol):
    """Minimal interface for LangChain-style chat models."""

    def invoke(self, prompt: str) -> Any:
        """Send a prompt and return a response object with extractable text."""


class _HTMLTextExtractor(HTMLParser):
    """Convert Confluence storage HTML to plain text."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect text nodes."""
        if data.strip():
            self._parts.append(data.strip())

    def get_text(self) -> str:
        """Return normalized plain text."""
        return unescape(" ".join(self._parts))


class ConfluenceChunker:
    """Fetch Confluence policy pages, chunk by section, and extract OWL axioms."""

    def __init__(self, confluence_url: str, username: str, api_token: str) -> None:
        """Initialise the Atlassian Confluence REST client.

        Args:
            confluence_url: Base Confluence URL (for example
                ``https://example.atlassian.net/wiki``).
            username: Confluence account email for API authentication.
            api_token: Confluence API token.
        """
        try:
            from atlassian import Confluence
        except ImportError as exc:
            raise ImportError(
                "atlassian-python-api is required. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from exc

        self._confluence_url = confluence_url.rstrip("/")
        self._client = Confluence(
            url=self._confluence_url,
            username=username,
            password=api_token,
            cloud=True,
        )

    def get_pages(self, space_key: str) -> list[dict[str, Any]]:
        """Fetch all pages from a Confluence space.

        Args:
            space_key: Confluence space key (for example ``KYC``).

        Returns:
            Page dictionaries with ``title``, ``body`` (plain text), ``version``,
            and ``url``.
        """
        pages: list[dict[str, Any]] = []
        start = 0
        limit = 50

        while True:
            batch = self._client.get_all_pages_from_space(
                space_key,
                start=start,
                limit=limit,
                expand="body.storage,version",
            )
            if not batch:
                break

            for raw_page in batch:
                page_id = str(raw_page.get("id", ""))
                title = raw_page.get("title", "")
                version = raw_page.get("version", {}).get("number", 1)
                storage = raw_page.get("body", {}).get("storage", {})
                html_body = storage.get("value", "")
                pages.append(
                    {
                        "title": title,
                        "body": self._html_to_text(html_body),
                        "version": version,
                        "url": self._page_url(page_id),
                    }
                )

            if len(batch) < limit:
                break
            start += limit

        return pages

    def chunk_by_section(self, page: dict[str, Any]) -> list[dict[str, Any]]:
        """Split a page body into numbered policy sections.

        Sections are split on headings that match ``\\d+.\\d+`` at line start,
        for example ``3.1 Customer identification``.

        Args:
            page: Page dictionary from :meth:`get_pages`.

        Returns:
            Chunk dictionaries with ``content``, ``section_heading``,
            ``page_title``, ``page_url``, ``version``, and ``confidence``.
        """
        body = page.get("body", "").strip()
        if not body:
            return []

        parts = _SECTION_SPLIT_RE.split(body)
        chunks: list[dict[str, Any]] = []

        for part in parts:
            content = part.strip()
            if not content:
                continue

            heading_match = _SECTION_HEADING_RE.match(content)
            section_heading = (
                heading_match.group(1).strip() if heading_match else page.get("title", "")
            )

            chunks.append(
                {
                    "content": content,
                    "section_heading": section_heading,
                    "page_title": page.get("title", ""),
                    "page_url": page.get("url", ""),
                    "version": page.get("version", 1),
                    "confidence": 0.70,
                }
            )

        return chunks

    def to_owl_prompt(self, chunk: dict[str, Any]) -> str:
        """Build an LLM prompt for OWL extraction from one section chunk.

        Args:
            chunk: Section chunk from :meth:`chunk_by_section`.

        Returns:
            Structured prompt instructing Turtle-only output with SOURCE and
            ASSUMPTION annotations.
        """
        return "\n".join(
            [
                "Extract KYC compliance ontology axioms from the Confluence section below.",
                "Output only valid Turtle syntax.",
                "For every inference you make, add <!-- ASSUMPTION: reason -->",
                (
                    "For every proposed axiom, add "
                    f"<!-- SOURCE: {chunk['page_url']} {chunk['section_heading']} -->"
                ),
                "",
                f"Page title: {chunk['page_title']}",
                f"Section heading: {chunk['section_heading']}",
                f"Page version: {chunk['version']}",
                f"Extraction confidence: {chunk['confidence']}",
                "",
                "Section content:",
                chunk["content"],
            ]
        )

    def extract(self, space_key: str, llm: LLMClient, output_path: str) -> None:
        """Run the full Confluence-to-Turtle extraction pipeline.

        Args:
            space_key: Confluence space key to scan.
            llm: Chat model implementing ``invoke(prompt)``.
            output_path: Destination path for merged Turtle output.
        """
        pages = self.get_pages(space_key)
        all_chunks: list[dict[str, Any]] = []

        for page in pages:
            all_chunks.extend(self.chunk_by_section(page))

        total = len(all_chunks)
        if total == 0:
            Path(output_path).write_text(
                f"# No Confluence chunks found in space {space_key!r}.\n",
                encoding="utf-8",
            )
            return

        lines = [
            "# KYC ontology candidates extracted from Confluence",
            f"# Space: {space_key}",
            "",
        ]

        for index, chunk in enumerate(all_chunks, start=1):
            heading = chunk["section_heading"]
            print(f"Extracted chunk {index} of {total}: {heading}")
            response = llm.invoke(self.to_owl_prompt(chunk))
            turtle = self._response_to_text(response).strip()
            lines.append(f"# --- {chunk['page_title']} :: {heading} ---")
            lines.append(turtle)
            lines.append("")

        Path(output_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _page_url(self, page_id: str) -> str:
        """Build a view URL for a Confluence page id."""
        return f"{self._confluence_url}/pages/viewpage.action?pageId={page_id}"

    def _html_to_text(self, html_body: str) -> str:
        """Strip HTML tags and normalize whitespace."""
        parser = _HTMLTextExtractor()
        parser.feed(html_body)
        text = parser.get_text()
        return re.sub(r"\s+\n", "\n", text).strip()

    def _response_to_text(self, response: Any) -> str:
        """Normalize LangChain or plain-string LLM responses to text."""
        if isinstance(response, str):
            text = response
        elif hasattr(response, "content"):
            content = response.content
            text = content if isinstance(content, str) else str(content)
        else:
            text = str(response)

        fenced = re.search(r"```(?:turtle|ttl)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        return text


def _build_default_llm() -> LLMClient:
    """Construct the default Anthropic chat model from environment configuration."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise SystemExit(
            "langchain-anthropic is required for CLI extraction. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    return ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


def main() -> None:
    """CLI entry point for Confluence chunk extraction."""
    parser = argparse.ArgumentParser(
        description="Chunk Confluence KYC policy pages and extract Turtle via LLM."
    )
    parser.add_argument("--space", required=True, help="Confluence space key")
    parser.add_argument("--output", required=True, help="Output Turtle file path")
    parser.add_argument(
        "--confluence-url",
        default=os.environ.get("CONFLUENCE_URL", ""),
        help="Confluence base URL (or set CONFLUENCE_URL)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("CONFLUENCE_USERNAME", ""),
        help="Confluence username/email (or set CONFLUENCE_USERNAME)",
    )
    parser.add_argument(
        "--api-token",
        default=os.environ.get("CONFLUENCE_API_TOKEN", ""),
        help="Confluence API token (or set CONFLUENCE_API_TOKEN)",
    )
    args = parser.parse_args()

    if not args.confluence_url or not args.username or not args.api_token:
        raise SystemExit(
            "Confluence credentials required: pass --confluence-url, --username, "
            "and --api-token or set CONFLUENCE_URL, CONFLUENCE_USERNAME, "
            "and CONFLUENCE_API_TOKEN."
        )

    chunker = ConfluenceChunker(args.confluence_url, args.username, args.api_token)
    chunker.extract(args.space, _build_default_llm(), args.output)


if __name__ == "__main__":
    main()
