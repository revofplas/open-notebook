"""Oracle HR Database client.

Uses python-oracledb in thin mode — Oracle Instant Client not required.
Maintains an async connection pool for the API process lifetime.
"""

import os
from typing import Optional

import oracledb
from loguru import logger

_pool: Optional[oracledb.AsyncConnectionPool] = None


async def get_pool() -> oracledb.AsyncConnectionPool:
    global _pool
    if _pool is not None:
        return _pool

    dsn = os.getenv("ORACLE_DSN")          # e.g. "192.168.x.x:1521/HRDB"
    user = os.getenv("ORACLE_USER")         # 서비스 계정 (읽기 전용)
    password = os.getenv("ORACLE_PASSWORD")

    if not all([dsn, user, password]):
        raise RuntimeError(
            "Oracle connection not configured. "
            "Set ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD in environment."
        )

    logger.info(f"Creating Oracle connection pool: dsn={dsn}, user={user}")
    _pool = await oracledb.create_pool_async(
        user=user,
        password=password,
        dsn=dsn,
        min=int(os.getenv("ORACLE_POOL_MIN", "2")),
        max=int(os.getenv("ORACLE_POOL_MAX", "10")),
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
