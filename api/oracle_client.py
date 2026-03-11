"""Oracle HR Database client.

Uses python-oracledb in thin mode — Oracle Instant Client not required.
Maintains an async connection pool for the API process lifetime.

Config priority: SurrealDB oracle_config table > environment variables.
"""

import os
from typing import Optional

import oracledb
from loguru import logger

_pool: Optional[oracledb.AsyncConnectionPool] = None


async def _get_oracle_config_from_db() -> Optional[dict]:
    """Try to load Oracle config from SurrealDB oracle_config table."""
    try:
        from open_notebook.database.repository import repo_query
        result = await repo_query("SELECT * FROM oracle_config:default LIMIT 1")
        if result and result[0].get("enabled") and result[0].get("dsn"):
            return result[0]
    except Exception as e:
        logger.debug(f"Could not read oracle_config from DB (using env vars): {e}")
    return None


async def get_pool() -> oracledb.AsyncConnectionPool:
    global _pool
    if _pool is not None:
        return _pool

    # Try DB config first, fall back to env vars
    db_config = await _get_oracle_config_from_db()
    if db_config:
        dsn = db_config.get("dsn")
        user = db_config.get("username")
        password = db_config.get("password")
        pool_min = int(db_config.get("pool_min", 2))
        pool_max = int(db_config.get("pool_max", 10))
        logger.info("Using Oracle config from database")
    else:
        dsn = os.getenv("ORACLE_DSN")
        user = os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD")
        pool_min = int(os.getenv("ORACLE_POOL_MIN", "2"))
        pool_max = int(os.getenv("ORACLE_POOL_MAX", "10"))

    if not all([dsn, user, password]):
        raise RuntimeError(
            "Oracle connection not configured. "
            "Set ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD in environment "
            "or configure via Admin > Oracle Settings."
        )

    logger.info(f"Creating Oracle connection pool: dsn={dsn}, user={user}")
    _pool = await oracledb.create_pool_async(
        user=user,
        password=password,
        dsn=dsn,
        min=pool_min,
        max=pool_max,
        increment=1,
    )
    logger.success("Oracle connection pool ready")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Oracle connection pool closed")


async def reset_pool() -> None:
    """Close and reset the pool so it will be re-created with new config."""
    await close_pool()


async def fetch_employee_by_user_id(user_id: str) -> Optional[dict]:
    """INF.VI_INF_EMP_INFO 에서 USER_ID 기준으로 재직 중인 직원 조회."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT EMP_NO, EMP_NM, USER_ID, PWD,
                       DEPT_CD, DEPT_NM, EMAIL,
                       GRD_NM, JOB_TP_NM, USE_YN, HOLD_OFFI
                FROM   INF.VI_INF_EMP_INFO
                WHERE  USER_ID = :user_id
                AND    USE_YN  = 'Y'
                """,
                user_id=user_id,
            )
            row = await cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
