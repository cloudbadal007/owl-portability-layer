"""ServiceNow Context Engine Adapter for the OWL Portability Layer.

ServiceNow's CMDB lineage (22 years) remains a practical advantage for
enterprise relationship and lifecycle data modeling at scale.

The newer Knowledge Graph capability does not yet support ``cmdb_rel_ci``
relationships the way CMDB does — this is a known gap as of Knowledge 2026.

When you leave ServiceNow, delete this file.
Your OWL ontology and SHACL constraints remain unchanged.

Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

from typing import Any

import httpx

from owl_portability.adapters.base import BaseAdapter


class ServiceNowContextEngineAdapter(BaseAdapter):
    """Adapter for ServiceNow Context Engine / Table API writes and reads."""

    OWL_TO_TABLE_MAP: dict[str, str] = {
        "PaymentEvent": "fm_expense_line",
        "Vendor": "core_company",
        "Contract": "ast_contract",
        "EmployeeOffboarding": "sn_hr_core_case_offboarding",
        "ITDomain": "cmdb_ci",
        "HRDomain": "sn_hr_core_case",
        "ComplianceHold": "sn_compliance_task",
        "ChangeRecord": "change_request",
        "Incident": "incident",
        "ServiceDependency": "cmdb_rel_ci",
    }

    def __init__(
        self,
        instance_url: str,
        username: str,
        password: str,
        simulation_mode: bool = True,
    ) -> None:
        """Initialize ServiceNow credentials and simulation behavior.

        Args:
            instance_url: ServiceNow instance base URL.
            username: ServiceNow username for Basic Auth.
            password: ServiceNow password for Basic Auth.
            simulation_mode: If True, print simulated calls and avoid HTTP requests.
        """
        self._instance_url = instance_url.rstrip("/")
        self._username = username
        self._password = password
        self._simulation_mode = simulation_mode

    @property
    def platform_name(self) -> str:
        """Return stable adapter platform identifier."""
        return "servicenow_context_engine"

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Write one OWL entity to the mapped ServiceNow table.

        Args:
            entity_data: Entity payload data.
            entity_class: OWL class name.

        Returns:
            True on success, False on error.
        """
        table = self.OWL_TO_TABLE_MAP.get(entity_class, "u_owl_entity")
        payload = {key: str(value) for key, value in entity_data.items()}
        payload["u_owl_class"] = entity_class
        payload["u_owl_validated"] = "true"
        payload["u_shacl_passed"] = "true"

        if self._simulation_mode:
            print("[ServiceNow simulation] write")
            print(f"  table={table}")
            print(f"  owl_class={entity_class}")
            print(f"  payload={payload}")
            return True

        url = f"{self._instance_url}/api/now/table/{table}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=headers,
                    auth=(self._username, self._password),
                )
            response.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            print(f"ServiceNow write failed for class {entity_class} table {table}: {exc}")
            return False

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Read entities from the mapped ServiceNow table.

        Args:
            entity_class: OWL class name.
            filters: Key/value filters for ServiceNow query.

        Returns:
            List of matching records (or simulation placeholders).
        """
        table = self.OWL_TO_TABLE_MAP.get(entity_class, "u_owl_entity")
        if self._simulation_mode:
            return [
                {
                    "entity_class": entity_class,
                    "source": "servicenow",
                    "simulation": True,
                }
            ]

        query = "^".join(f"{key}={value}" for key, value in filters.items())
        params = {"sysparm_query": query, "sysparm_limit": 100}
        url = f"{self._instance_url}/api/now/table/{table}"
        headers = {"Accept": "application/json"}
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(
                    url,
                    params=params,
                    headers=headers,
                    auth=(self._username, self._password),
                )
            response.raise_for_status()
            data = response.json()
            return data.get("result", [])
        except (httpx.HTTPError, ValueError) as exc:
            print(f"ServiceNow read failed for class {entity_class} table {table}: {exc}")
            return []

    def health_check(self) -> bool:
        """Check adapter connectivity to ServiceNow."""
        if self._simulation_mode:
            return True
        url = f"{self._instance_url}/api/now/table/sys_user?sysparm_limit=1"
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, auth=(self._username, self._password))
            return response.status_code == 200
        except httpx.HTTPError:
            return False
