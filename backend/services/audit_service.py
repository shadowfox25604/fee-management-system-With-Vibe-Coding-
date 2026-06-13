from __future__ import annotations

import json

from backend.models.entities import AuditLog


class AuditService:
    def __init__(self, session, *, performed_by: str = "system") -> None:
        self.session = session
        self.performed_by = performed_by

    def log_action(
        self,
        action: str,
        table_name: str,
        record_id: str,
        *,
        old_value: object = "",
        new_value: object = "",
        performed_by: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            table_name=table_name,
            record_id=str(record_id),
            old_value=self._serialize(old_value),
            new_value=self._serialize(new_value),
            performed_by=performed_by or self.performed_by,
        )
        self.session.add(entry)
        return entry

    @staticmethod
    def _serialize(value: object) -> str:
        if value == "" or value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, default=str, ensure_ascii=True)
