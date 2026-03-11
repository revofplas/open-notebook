"""Audit log service.

Writes audit_log records asynchronously. Failures are logged but never
propagate — audit logging must not break business flows.
"""

from typing import Any, Optional

from loguru import logger

from open_notebook.database.repository import repo_query


async def write_audit_log(
    user_id: str,
    action: str,
    resource: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    ip: Optional[str] = None,
) -> None:
    """
    감사로그를 audit_log 테이블에 기록합니다.

    Args:
        user_id: SurrealDB user record id (e.g. "user:abc123")
        action:  동작 코드 — 'login' | 'logout' | 'create_notebook' |
                 'delete_notebook' | 'upload_source' | 'delete_source' |
                 'search' | 'chat' 등
        resource: 대상 리소스 id (선택)
        meta:     추가 컨텍스트 (선택)
        ip:       클라이언트 IP (선택)
    """
    try:
        from open_notebook.database.repository import ensure_record_id
        await repo_query(
            """
            CREATE audit_log CONTENT {
                user_id:  $user_id,
                action:   $action,
                resource: $resource,
                meta:     $meta,
                ip:       $ip,
                ts:       time::now()
            }
            """,
            {
                "user_id": ensure_record_id(user_id),
                "action": action,
                "resource": resource,
                "meta": meta,
                "ip": ip,
            },
        )
    except Exception as e:
        logger.warning(f"Audit log write failed (action={action}, user={user_id}): {e}")
