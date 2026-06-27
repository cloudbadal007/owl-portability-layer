"""Filter compliance Slack messages and detect superseded rulings."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Protocol


class LLMClient(Protocol):
    """Minimal interface for LangChain-style chat models."""

    def invoke(self, prompt: str) -> Any:
        """Send a prompt and return a response object with extractable text."""


class SlackFilter:
    """Fetch Slack compliance messages, detect conflicts, and build OWL prompts."""

    def __init__(self, bot_token: str) -> None:
        """Initialise the Slack Web API client.

        Args:
            bot_token: Slack bot token with channel history read access.
        """
        try:
            from slack_sdk import WebClient
        except ImportError as exc:
            raise ImportError(
                "slack-sdk is required. Install dependencies with: pip install -r requirements.txt"
            ) from exc

        self._client = WebClient(token=bot_token)

    def get_messages(self, channel_id: str, days_back: int = 90) -> list[dict[str, Any]]:
        """Fetch channel messages within a lookback window.

        Excludes bot messages, ``file_share`` subtypes, and messages shorter
        than 30 characters.

        Args:
            channel_id: Slack channel ID.
            days_back: Number of days of history to retrieve.

        Returns:
            Message dictionaries with ``text``, ``user``, ``ts``, and
            ``thread_ts``.
        """
        oldest = str(time.time() - days_back * 86_400)
        messages: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            response = self._client.conversations_history(
                channel=channel_id,
                oldest=oldest,
                limit=200,
                cursor=cursor,
            )
            for raw in response.get("messages", []):
                if self._should_exclude(raw):
                    continue
                messages.append(
                    {
                        "text": raw.get("text", "").strip(),
                        "user": raw.get("user", ""),
                        "ts": raw.get("ts", ""),
                        "thread_ts": raw.get("thread_ts", raw.get("ts", "")),
                    }
                )

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        messages.sort(key=lambda item: float(item["ts"]))
        return messages

    def detect_conflicts(self, messages: list[dict[str, Any]], llm: LLMClient) -> list[dict[str, Any]]:
        """Identify contradictory Slack messages using chronological LLM review.

        The model is instructed to treat the more recent message as authoritative
        unless an explicit statement overrides that default.

        Args:
            messages: Chronologically sortable message list from
                :meth:`get_messages`.
            llm: Chat model implementing ``invoke(prompt)``.

        Returns:
            Conflict dictionaries with ``earlier_ts``, ``later_ts``,
            ``description``, and ``authoritative_ts``.
        """
        if not messages:
            return []

        sorted_messages = sorted(messages, key=lambda item: float(item["ts"]))
        prompt = self._conflict_detection_prompt(sorted_messages)
        response = llm.invoke(prompt)
        return self._parse_conflict_response(response)

    def to_owl_prompt(
        self,
        messages: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
    ) -> str:
        """Format active Slack messages for OWL axiom extraction.

        Messages superseded by conflict resolution are excluded before prompt
        construction.

        Args:
            messages: Full message list from :meth:`get_messages`.
            conflicts: Conflict list from :meth:`detect_conflicts`.

        Returns:
            Structured prompt for Turtle extraction with SOURCE and ASSUMPTION
            annotation requirements.
        """
        superseded_ts = {conflict["earlier_ts"] for conflict in conflicts}
        active_messages = [message for message in messages if message["ts"] not in superseded_ts]
        active_messages.sort(key=lambda item: float(item["ts"]))

        lines = [
            "Extract KYC compliance ontology axioms from the Slack messages below.",
            "Output only valid Turtle syntax.",
            "For every inference you make, add <!-- ASSUMPTION: reason -->",
            "For every proposed axiom, add <!-- SOURCE: Slack ts={ts} --> using the source timestamp.",
            "Slack-derived axioms have confidence 0.40 — flag all for domain expert review.",
            "",
            f"Active messages after conflict filtering: {len(active_messages)}",
            f"Superseded messages excluded: {len(superseded_ts)}",
            "",
        ]

        if conflicts:
            lines.append("Detected conflicts (authoritative message retained):")
            for conflict in conflicts:
                lines.append(
                    f"  - {conflict['description']} "
                    f"(authoritative ts={conflict['authoritative_ts']})"
                )
            lines.append("")

        for message in active_messages:
            lines.append(
                f"[ts={message['ts']} user={message['user']}] {message['text']}"
            )

        return "\n".join(lines)

    def extract(
        self,
        channel_id: str,
        days_back: int,
        llm: LLMClient,
        output_path: str,
    ) -> None:
        """Run Slack fetch, conflict detection, and Turtle extraction.

        Args:
            channel_id: Slack channel ID.
            days_back: History lookback in days.
            llm: Chat model implementing ``invoke(prompt)``.
            output_path: Destination path for Turtle output.
        """
        messages = self.get_messages(channel_id, days_back=days_back)
        print(f"Fetched {len(messages)} Slack messages from the last {days_back} days.")
        conflicts = self.detect_conflicts(messages, llm)
        print(f"Detected {len(conflicts)} conflicting message pairs.")
        prompt = self.to_owl_prompt(messages, conflicts)
        response = llm.invoke(prompt)
        turtle = self._response_to_text(response).strip()

        output = "\n".join(
            [
                "# KYC ontology candidates extracted from Slack",
                f"# Channel: {channel_id}",
                f"# Lookback days: {days_back}",
                "",
                turtle,
                "",
            ]
        )
        Path(output_path).write_text(output, encoding="utf-8")

    def _should_exclude(self, message: dict[str, Any]) -> bool:
        """Return True when a raw Slack message should be skipped."""
        if message.get("bot_id") or message.get("subtype") == "bot_message":
            return True
        if message.get("subtype") == "file_share":
            return True
        text = message.get("text", "").strip()
        return len(text) < 30

    def _conflict_detection_prompt(self, messages: list[dict[str, Any]]) -> str:
        """Build the conflict-detection prompt for the LLM."""
        payload = json.dumps(messages, indent=2)
        return "\n".join(
            [
                "Review the Slack compliance messages below in chronological order.",
                "Identify any message that contradicts an earlier message on policy or procedure.",
                "For each conflict, note both timestamps.",
                "Treat the more recent message as authoritative unless an explicit statement",
                "in the thread says otherwise.",
                "",
                "Return ONLY a JSON array. Each object must contain:",
                "  earlier_ts, later_ts, description, authoritative_ts",
                "If there are no conflicts, return [].",
                "",
                "Messages:",
                payload,
            ]
        )

    def _parse_conflict_response(self, response: Any) -> list[dict[str, Any]]:
        """Parse the LLM JSON conflict array from a model response."""
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

        conflicts: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            required = {"earlier_ts", "later_ts", "description", "authoritative_ts"}
            if not required.issubset(item.keys()):
                continue
            conflicts.append(
                {
                    "earlier_ts": str(item["earlier_ts"]),
                    "later_ts": str(item["later_ts"]),
                    "description": str(item["description"]),
                    "authoritative_ts": str(item["authoritative_ts"]),
                }
            )
        return conflicts

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
            "langchain-anthropic is required for CLI extraction. "
            "Install dependencies with: pip install -r requirements.txt"
        ) from exc

    return ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)


def main() -> None:
    """CLI entry point for Slack filtering and Turtle extraction."""
    parser = argparse.ArgumentParser(
        description="Filter Slack KYC messages and extract Turtle via LLM."
    )
    parser.add_argument("--channel", required=True, help="Slack channel ID")
    parser.add_argument("--days", type=int, default=90, help="Lookback window in days")
    parser.add_argument("--output", required=True, help="Output Turtle file path")
    parser.add_argument(
        "--bot-token",
        default=os.environ.get("SLACK_BOT_TOKEN", ""),
        help="Slack bot token (or set SLACK_BOT_TOKEN)",
    )
    args = parser.parse_args()

    if not args.bot_token:
        raise SystemExit("Slack bot token required: pass --bot-token or set SLACK_BOT_TOKEN.")

    slack_filter = SlackFilter(args.bot_token)
    slack_filter.extract(args.channel, args.days, _build_default_llm(), args.output)


if __name__ == "__main__":
    main()
