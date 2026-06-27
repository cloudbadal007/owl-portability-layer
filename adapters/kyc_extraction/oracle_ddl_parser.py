"""Parse Oracle/PostgreSQL DDL and propose OWL classes and properties."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


ASSUMPTION_INSTRUCTION = (
    "For every inference you make, add <!-- ASSUMPTION: reason -->\n"
    "For every constraint you cannot represent in OWL DL, add "
    "<!-- LIMITATION: reason -->"
)

_CREATE_TABLE_RE = re.compile(
    r"""
    CREATE\s+TABLE\s+
    (?:(?P<schema>"[^"]+"|\w+)\s*\.\s*)?
    (?P<table>"[^"]+"|\w+)
    \s*\(
    """,
    re.IGNORECASE | re.VERBOSE,
)

_INLINE_REF_RE = re.compile(
    r"""
    REFERENCES\s+
    (?P<to_table>"[^"]+"|\w+)
    \s*\(\s*(?P<to_col>"[^"]+"|\w+)\s*\)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_FK_CONSTRAINT_RE = re.compile(
    r"""
    (?:CONSTRAINT\s+(?:"[^"]+"|\w+)\s+)?FOREIGN\s+KEY\s*\(
        (?P<from_cols>[^)]+)
    \)\s*REFERENCES\s+
    (?P<to_table>"[^"]+"|\w+)
    \s*\(\s*(?P<to_cols>[^)]+)\s*\)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_CHECK_RE = re.compile(r"CHECK\s*\((.+)\)\s*$", re.IGNORECASE | re.DOTALL)

_COLUMN_START_RE = re.compile(r'^("?\w+"?)\s+(.+)$', re.DOTALL)


class LLMClient(Protocol):
    """Minimal interface for LangChain-style chat models."""

    def invoke(self, prompt: str) -> Any:
        """Send a prompt and return a response object with extractable text."""


@dataclass
class ParsedTable:
    """Internal representation of one parsed DDL table."""

    table_name: str
    columns: list[dict[str, Any]] = field(default_factory=list)
    foreign_keys: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the public parse_ddl dictionary shape."""
        return {
            "table_name": self.table_name,
            "columns": list(self.columns),
            "foreign_keys": list(self.foreign_keys),
        }


class OracleDDLParser:
    """Extract structured table metadata from Oracle-style DDL and build OWL prompts."""

    def parse_ddl(self, ddl_text: str) -> list[dict[str, Any]]:
        """Parse Oracle-style DDL into structured table metadata.

        Uses regex and balanced-parenthesis scanning to extract ``CREATE TABLE``
        blocks, column definitions, inline ``CHECK`` constraints, and
        ``REFERENCES`` foreign keys.

        Args:
            ddl_text: Raw DDL script text.

        Returns:
            One dictionary per table with keys ``table_name``, ``columns``, and
            ``foreign_keys``. Each column dict has ``name``, ``type``,
            ``nullable``, and optional ``check``. Each foreign key dict has
            ``from_col``, ``to_table``, and ``to_col``.
        """
        cleaned = self._strip_sql_comments(ddl_text)
        tables: list[ParsedTable] = []

        for match in _CREATE_TABLE_RE.finditer(cleaned):
            table_name = self._unquote(match.group("table"))
            start = match.end()
            body, _ = self._read_balanced_block(cleaned, start - 1)
            if body is None:
                continue
            inner = body[1:-1]
            parsed = ParsedTable(table_name=table_name)
            self._parse_table_body(inner, parsed)
            tables.append(parsed)

        return [table.to_dict() for table in tables]

    def to_owl_prompt(self, parsed_tables: list[dict[str, Any]]) -> str:
        """Format one parsed table as an LLM prompt for OWL/Turtle extraction.

        Builds a single-table prompt chunk. Callers must pass exactly one table
        dictionary per invocation.

        Args:
            parsed_tables: List containing one table dict from :meth:`parse_ddl`.

        Returns:
            Structured prompt string with ASSUMPTION/LIMITATION instructions.

        Raises:
            ValueError: If ``parsed_tables`` does not contain exactly one table.
        """
        if len(parsed_tables) != 1:
            raise ValueError(
                "to_owl_prompt expects exactly one table per prompt chunk; "
                f"received {len(parsed_tables)}."
            )

        table = parsed_tables[0]
        lines = [
            ASSUMPTION_INSTRUCTION,
            "",
            "You are extracting OWL 2 DL classes and properties for a KYC compliance ontology.",
            "Return valid Turtle syntax only. Use a stable namespace prefix:",
            "@prefix kyc: <http://enterprise.org/kyc#> .",
            "",
            f"Source table: {table['table_name']}",
            "",
            "Columns:",
        ]

        for column in table.get("columns", []):
            nullable = "nullable" if column.get("nullable", True) else "NOT NULL"
            line = f"  - {column['name']}: {column['type']} ({nullable})"
            if column.get("check"):
                line += f" CHECK {column['check']}"
            lines.append(line)

        foreign_keys = table.get("foreign_keys", [])
        if foreign_keys:
            lines.append("")
            lines.append("Foreign keys:")
            for fk in foreign_keys:
                lines.append(
                    f"  - {fk['from_col']} -> {fk['to_table']}.{fk['to_col']}"
                )

        lines.extend(
            [
                "",
                "Map this table to one OWL class and columns to datatype or object properties.",
                "Represent foreign keys as object properties where appropriate.",
                "Preserve CHECK constraints as comments or OWL restrictions when possible.",
                f"Name the primary class after the business meaning of table {table['table_name']}.",
            ]
        )
        return "\n".join(lines)

    def extract(self, ddl_path: str, llm: LLMClient, output_path: str) -> None:
        """Run the full DDL-to-Turtle extraction pipeline.

        Reads DDL from disk, parses tables, prompts the LLM once per table,
        and writes the combined Turtle output.

        Args:
            ddl_path: Path to a ``.sql`` DDL file.
            llm: Chat model implementing ``invoke(prompt)``.
            output_path: Destination path for merged Turtle output.
        """
        ddl_text = Path(ddl_path).read_text(encoding="utf-8")
        parsed_tables = self.parse_ddl(ddl_text)
        total = len(parsed_tables)

        if total == 0:
            Path(output_path).write_text(
                "# No CREATE TABLE statements found in DDL.\n",
                encoding="utf-8",
            )
            return

        chunks: list[str] = [
            "# KYC ontology draft extracted from Oracle DDL",
            f"# Source: {ddl_path}",
            "",
        ]

        for index, table in enumerate(parsed_tables, start=1):
            table_name = table["table_name"]
            print(f"Extracted table {index} of {total}: {table_name}")
            prompt = self.to_owl_prompt([table])
            response = llm.invoke(prompt)
            turtle = self._response_to_text(response).strip()
            chunks.append(f"# --- Table: {table_name} ---")
            chunks.append(turtle)
            chunks.append("")

        Path(output_path).write_text("\n".join(chunks).rstrip() + "\n", encoding="utf-8")

    def _parse_table_body(self, body: str, table: ParsedTable) -> None:
        """Populate columns and foreign keys from a CREATE TABLE body."""
        for definition in self._split_top_level(body):
            upper = definition.upper()
            if _FK_CONSTRAINT_RE.search(definition):
                self._parse_foreign_key_constraint(definition, table)
                continue
            if upper.startswith("CONSTRAINT ") and " CHECK " in upper:
                self._parse_table_check_constraint(definition, table)
                continue
            if upper.startswith(("PRIMARY KEY", "UNIQUE ", "CHECK ", "FOREIGN KEY")):
                if upper.startswith("FOREIGN KEY"):
                    self._parse_foreign_key_constraint(definition, table)
                continue

            column = self._parse_column_definition(definition)
            if column is not None:
                table.columns.append(column)
                ref_match = _INLINE_REF_RE.search(definition)
                if ref_match:
                    table.foreign_keys.append(
                        {
                            "from_col": column["name"],
                            "to_table": self._unquote(ref_match.group("to_table")),
                            "to_col": self._unquote(ref_match.group("to_col")),
                        }
                    )

    def _parse_column_definition(self, definition: str) -> dict[str, Any] | None:
        """Parse a single column definition line."""
        match = _COLUMN_START_RE.match(definition.strip())
        if not match:
            return None

        name = self._unquote(match.group(1))
        remainder = match.group(2).strip()
        upper = remainder.upper()

        if upper.startswith(("CONSTRAINT ", "PRIMARY KEY", "FOREIGN KEY", "UNIQUE ", "CHECK ")):
            return None

        data_type, tail = self._split_type_and_constraints(remainder)
        nullable = "NOT NULL" not in upper
        if "PRIMARY KEY" in upper:
            nullable = False

        check_match = _CHECK_RE.search(tail)
        check_expr = check_match.group(1).strip() if check_match else None

        column: dict[str, Any] = {
            "name": name,
            "type": data_type,
            "nullable": nullable,
        }
        if check_expr:
            column["check"] = check_expr

        return column

    def _parse_foreign_key_constraint(self, definition: str, table: ParsedTable) -> None:
        """Extract foreign key metadata from a table-level constraint."""
        match = _FK_CONSTRAINT_RE.search(definition)
        if not match:
            return

        from_cols = [self._unquote(part.strip()) for part in match.group("from_cols").split(",")]
        to_cols = [self._unquote(part.strip()) for part in match.group("to_cols").split(",")]
        to_table = self._unquote(match.group("to_table"))

        for from_col, to_col in zip(from_cols, to_cols, strict=False):
            table.foreign_keys.append(
                {
                    "from_col": from_col,
                    "to_table": to_table,
                    "to_col": to_col,
                }
            )

    def _parse_table_check_constraint(self, definition: str, table: ParsedTable) -> None:
        """Attach a table-level CHECK constraint to a synthetic note column when needed."""
        check_match = _CHECK_RE.search(definition)
        if not check_match:
            return
        table.columns.append(
            {
                "name": "__table_check__",
                "type": "CONSTRAINT",
                "nullable": True,
                "check": check_match.group(1).strip(),
            }
        )

    def _split_type_and_constraints(self, remainder: str) -> tuple[str, str]:
        """Separate the SQL data type from trailing column constraints."""
        tokens = remainder.split()
        if not tokens:
            return remainder, ""

        type_parts: list[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            upper = token.upper()
            if index > 0 and upper in {
                "DEFAULT",
                "NOT",
                "NULL",
                "CHECK",
                "REFERENCES",
                "PRIMARY",
                "KEY",
                "UNIQUE",
                "CONSTRAINT",
            }:
                break
            type_parts.append(token)
            index += 1
            if "(" in token and ")" not in token:
                while index < len(tokens) and ")" not in tokens[index]:
                    type_parts.append(tokens[index])
                    index += 1
                if index < len(tokens):
                    type_parts.append(tokens[index])
                    index += 1
                break

        data_type = " ".join(type_parts)
        tail = " ".join(tokens[index:])
        return data_type, tail

    def _strip_sql_comments(self, ddl_text: str) -> str:
        """Remove ``--`` line comments and ``/* */`` block comments."""
        without_block = re.sub(r"/\*.*?\*/", "", ddl_text, flags=re.DOTALL)
        lines = []
        for line in without_block.splitlines():
            if "--" in line:
                line = line.split("--", 1)[0]
            lines.append(line)
        return "\n".join(lines)

    def _read_balanced_block(self, text: str, open_index: int) -> tuple[str | None, int]:
        """Read a parenthesized block starting at ``open_index``."""
        if open_index >= len(text) or text[open_index] != "(":
            return None, open_index

        depth = 0
        for index in range(open_index, len(text)):
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[open_index : index + 1], index + 1
        return None, open_index

    def _split_top_level(self, body: str) -> list[str]:
        """Split CREATE TABLE body on commas outside nested parentheses."""
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        for char in body:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                piece = "".join(current).strip()
                if piece:
                    parts.append(piece)
                current = []
                continue
            current.append(char)

        piece = "".join(current).strip()
        if piece:
            parts.append(piece)
        return parts

    def _unquote(self, identifier: str) -> str:
        """Strip optional double quotes from a SQL identifier."""
        identifier = identifier.strip()
        if identifier.startswith('"') and identifier.endswith('"'):
            return identifier[1:-1]
        return identifier

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
    """CLI entry point for DDL-to-OWL extraction."""
    parser = argparse.ArgumentParser(
        description="Parse Oracle DDL and extract KYC ontology Turtle via LLM."
    )
    parser.add_argument("--ddl", required=True, help="Path to Oracle DDL .sql file")
    parser.add_argument("--output", required=True, help="Output Turtle file path")
    args = parser.parse_args()

    OracleDDLParser().extract(args.ddl, _build_default_llm(), args.output)


if __name__ == "__main__":
    main()
