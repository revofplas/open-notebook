"""Authentication service.

Handles:
  1. System admin login (SurrealDB, bcrypt)
  2. Oracle HR login (INF.VI_INF_EMP_INFO, custom SHA-512)
  3. JWT issuance / decoding
  4. User upsert on first login
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext

from api.oracle_client import fetch_employee_by_user_id
from open_notebook.database.repository import repo_query
from open_notebook.domain.user import User

# ── bcrypt for system admin accounts ──────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── JWT settings ──────────────────────────────────────────────────────────────
JWT_SECRET_KEY: str = os.getenv(
    "JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING"
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours


# ── Token helpers ──────────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user.user_id,
        "uid": str(user.id),
        "emp_no": user.emp_no,
        "emp_nm": user.emp_nm,
        "role": user.role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ── Password verification ──────────────────────────────────────────────────────

def verify_oracle_password(plain_password: str, stored_hash: str) -> bool:
    """
    Oracle HR 저장 비밀번호(INF.VI_INF_EMP_INFO.PWD)와 입력값을 비교합니다.

    알고리즘 (docs/99-KIMM-CUSTOMIZATION/ORACLE_PASSWD_VERIFICATION.md 참조):
      1. 입력 비밀번호를 SHA-512 해싱 후 Base64 인코딩
      2. DB 저장값의 선행 특수문자(^,`) 제거
      3. DB 저장값의 문자 치환: ] → /  ,  [ → +
      4. 두 값 비교
    """
    import base64
    import hashlib

    # Step 1: SHA-512 → Base64
    digest = hashlib.sha512(plain_password.encode("utf-8")).digest()
    user_hash = base64.b64encode(digest).decode("utf-8")

    # Step 2: 선행 특수문자 제거
    processed = stored_hash.lstrip("^,`")

    # Step 3: 문자 치환 (순서 중요: ] 먼저, 그 다음 [)
    processed = processed.replace("]", "/")
    processed = processed.replace("[", "+")

    # Step 4: 비교
    return user_hash == processed


# ── Main authentication entry point ───────────────────────────────────────────

async def authenticate_user(user_id: str, password: str) -> Optional[User]:
    """
    인증 흐름:
      1. SurrealDB에서 system admin 계정 확인 (bcrypt)
      2. Oracle HR 연동 (커스텀 SHA-512)
    성공 시 User 반환, 실패 시 None 반환.
    """
    # 1. System admin 우선 확인
    admin = await _find_system_admin(user_id)
    if admin:
        if _pwd_context.verify(password, admin.hashed_pw or ""):
            await _touch_last_login(admin.id)
            return admin
        logger.warning(f"Admin login failed: user_id={user_id}")
        return None

    # 2. Oracle HR 검증
    try:
        emp = await fetch_employee_by_user_id(user_id)
    except NotImplementedError:
        raise
    except Exception as e:
        logger.error(f"Oracle HR lookup error for user_id={user_id}: {e}")
        raise

    if not emp:
        logger.warning(f"Oracle HR: user not found or inactive — user_id={user_id}")
        return None

    if not verify_oracle_password(password, emp["PWD"]):
        logger.warning(f"Oracle HR: password mismatch — user_id={user_id}")
        return None

    # 3. SurrealDB에 사용자 upsert (최초 로그인 시 자동 생성)
    user = await _upsert_oracle_user(emp)
    await _touch_last_login(user.id)
    return user


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _find_system_admin(user_id: str) -> Optional[User]:
    try:
        rows = await repo_query(
            "SELECT * FROM user WHERE user_id = $uid AND source = 'system' LIMIT 1",
            {"uid": user_id},
        )
        return User(**rows[0]) if rows else None
    except Exception as e:
        logger.error(f"System admin lookup error for {user_id}: {e}")
        return None


async def _upsert_oracle_user(emp: dict) -> User:
    """Oracle HR 데이터로 SurrealDB user 레코드를 생성 또는 갱신합니다."""
    emp_no = emp["EMP_NO"]

    existing = await repo_query(
        "SELECT * FROM user WHERE emp_no = $emp_no LIMIT 1",
        {"emp_no": emp_no},
    )

    data = {
        "emp_no": emp_no,
        "user_id": emp["USER_ID"],
        "emp_nm": emp["EMP_NM"],
        "email": emp.get("EMAIL"),
        "dept_cd": emp.get("DEPT_CD"),
        "dept_nm": emp.get("DEPT_NM"),
        "grd_nm": emp.get("GRD_NM"),
        "job_tp_nm": emp.get("JOB_TP_NM"),
        "source": "oracle",
        "role": "member",
        "is_active": True,
    }

    if existing:
        rows = await repo_query(
            "UPDATE $id MERGE $data RETURN AFTER",
            {"id": existing[0]["id"], "data": data},
        )
    else:
        rows = await repo_query(
            "CREATE user CONTENT $data RETURN AFTER",
            {"data": data},
        )

    return User(**rows[0])


async def _touch_last_login(user_record_id: Optional[str]) -> None:
    if not user_record_id:
        return
    try:
        from open_notebook.database.repository import ensure_record_id
        await repo_query(
            "UPDATE $id SET last_login = time::now()",
            {"id": ensure_record_id(user_record_id)},
        )
    except Exception as e:
        logger.warning(f"last_login update failed for {user_record_id}: {e}")


# ── System admin bootstrap ─────────────────────────────────────────────────────

async def create_system_admin(
    user_id: str, emp_no: str, emp_nm: str, plain_password: str
) -> User:
    """
    시스템 독자 관리자 계정을 생성합니다.
    API 서버 최초 기동 시 또는 별도 관리 CLI에서 호출합니다.
    """
    hashed = _pwd_context.hash(plain_password)
    rows = await repo_query(
        "CREATE user CONTENT $data RETURN AFTER",
        {
            "data": {
                "user_id": user_id,
                "emp_no": emp_no,
                "emp_nm": emp_nm,
                "role": "admin",
                "source": "system",
                "hashed_pw": hashed,
                "is_active": True,
            }
        },
    )
    logger.success(f"System admin created: user_id={user_id}")
    return User(**rows[0])
