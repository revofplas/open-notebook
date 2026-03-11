"""Admin router — Oracle HR DB configuration and admin-only utilities."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from api.auth import require_admin
from open_notebook.database.repository import repo_query, repo_upsert

router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class OracleConfigResponse(BaseModel):
    dsn: str
    username: str
    pool_min: int
    pool_max: int
    enabled: bool
    # password is NEVER returned to the frontend


class OracleConfigUpdate(BaseModel):
    dsn: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None   # plain text; stored as-is (no frontend encryption needed here)
    pool_min: Optional[int] = None
    pool_max: Optional[int] = None
    enabled: Optional[bool] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/admin/oracle-config", response_model=OracleConfigResponse)
async def get_oracle_config(
    _admin: dict = Depends(require_admin),
):
    """Return current Oracle HR DB configuration (password omitted)."""
    try:
        result = await repo_query("SELECT * FROM oracle_config:default LIMIT 1")
        if not result:
            raise HTTPException(status_code=404, detail="Oracle config not found")
        cfg = result[0]
        return OracleConfigResponse(
            dsn=cfg.get("dsn", ""),
            username=cfg.get("username", ""),
            pool_min=int(cfg.get("pool_min", 2)),
            pool_max=int(cfg.get("pool_max", 10)),
            enabled=bool(cfg.get("enabled", False)),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Oracle config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load Oracle config: {e}")


@router.put("/admin/oracle-config", response_model=OracleConfigResponse)
async def update_oracle_config(
    config: OracleConfigUpdate,
    _admin: dict = Depends(require_admin),
):
    """Update Oracle HR DB configuration.  Resets the connection pool."""
    try:
        # Build update dict (only provided fields)
        update_data: dict = {}
        if config.dsn is not None:
            update_data["dsn"] = config.dsn
        if config.username is not None:
            update_data["username"] = config.username
        if config.password is not None and config.password.strip():
            update_data["password"] = config.password
        if config.pool_min is not None:
            update_data["pool_min"] = config.pool_min
        if config.pool_max is not None:
            update_data["pool_max"] = config.pool_max
        if config.enabled is not None:
            update_data["enabled"] = config.enabled

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        await repo_upsert("oracle_config", "default", update_data, add_timestamp=True)

        # Reset Oracle connection pool so it picks up new config on next use
        try:
            from api.oracle_client import reset_pool
            await reset_pool()
        except Exception as e:
            logger.warning(f"Could not reset Oracle pool (may not have been initialized): {e}")

        # Return updated config
        result = await repo_query("SELECT * FROM oracle_config:default LIMIT 1")
        cfg = result[0] if result else {}
        return OracleConfigResponse(
            dsn=cfg.get("dsn", ""),
            username=cfg.get("username", ""),
            pool_min=int(cfg.get("pool_min", 2)),
            pool_max=int(cfg.get("pool_max", 10)),
            enabled=bool(cfg.get("enabled", False)),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating Oracle config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update Oracle config: {e}")


@router.post("/admin/oracle-config/test")
async def test_oracle_connection(
    _admin: dict = Depends(require_admin),
):
    """Test the current Oracle HR DB connection."""
    try:
        from api.oracle_client import reset_pool, get_pool
        await reset_pool()  # force fresh pool with current config
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM DUAL")
                await cur.fetchone()
        return {"success": True, "message": "Oracle 연결 성공"}
    except Exception as e:
        logger.error(f"Oracle connection test failed: {e}")
        return {"success": False, "message": f"연결 실패: {str(e)}"}
