"""Authentication router.

Endpoints:
  POST /api/auth/login   — Oracle HR 또는 system admin 로그인 → JWT 반환
  GET  /api/auth/me      — 현재 사용자 정보
  POST /api/auth/logout  — 로그아웃 (클라이언트 측 토큰 파기 안내)
  GET  /api/auth/status  — 인증 활성화 여부 (프론트엔드 초기화용)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from api.audit_service import write_audit_log
from api.auth import get_current_user
from api.auth_service import authenticate_user, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    user_id: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Public endpoints ───────────────────────────────────────────────────────────

@router.get("/status")
async def get_auth_status():
    """프론트엔드 초기화 시 인증 방식 확인용."""
    return {
        "auth_enabled": True,
        "auth_type": "jwt",
        "message": "JWT authentication required",
    }


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request):
    """
    사번(USER_ID) + 비밀번호로 로그인.
    Oracle HR DB 검증 후 JWT를 반환합니다.
    시스템 관리자 계정은 SurrealDB에서 별도 검증합니다.
    """
    try:
        user = await authenticate_user(body.user_id, body.password)
    except Exception as e:
        logger.error(f"Login error for user_id={body.user_id}: {e}")
        raise HTTPException(status_code=503, detail="인증 서비스 오류가 발생했습니다.")

    if not user:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(user)

    ip = request.client.host if request.client else None
    await write_audit_log(str(user.id), "login", ip=ip)

    return LoginResponse(
        access_token=token,
        user={
            "uid": str(user.id),
            "user_id": user.user_id,
            "emp_no": user.emp_no,
            "emp_nm": user.emp_nm,
            "email": user.email,
            "dept_nm": user.dept_nm,
            "grd_nm": user.grd_nm,
            "role": user.role,
        },
    )


# ── Protected endpoints ────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """현재 로그인된 사용자 정보를 반환합니다."""
    return current_user


@router.post("/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """
    로그아웃 처리.
    JWT는 stateless이므로 서버 측 무효화 없이 클라이언트가 토큰을 삭제합니다.
    """
    ip = request.client.host if request.client else None
    await write_audit_log(current_user.get("uid", ""), "logout", ip=ip)
    return {"message": "로그아웃되었습니다."}
