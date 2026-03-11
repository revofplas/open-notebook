from datetime import datetime
from typing import ClassVar, List, Optional

from loguru import logger

from open_notebook.database.repository import repo_query
from open_notebook.domain.base import ObjectModel
from open_notebook.exceptions import DatabaseOperationError


class User(ObjectModel):
    table_name: ClassVar[str] = "user"
    nullable_fields: ClassVar[set[str]] = {
        "email", "dept_cd", "dept_nm", "grd_nm", "job_tp_nm",
        "hashed_pw", "last_login",
    }

    emp_no: str
    user_id: str
    emp_nm: str
    email: Optional[str] = None
    dept_cd: Optional[str] = None
    dept_nm: Optional[str] = None
    grd_nm: Optional[str] = None
    job_tp_nm: Optional[str] = None
    role: str = "member"          # 'member' | 'admin'
    source: str = "oracle"        # 'oracle' | 'system'
    hashed_pw: Optional[str] = None   # bcrypt hash, only for source='system'
    is_active: bool = True
    quota_files: int = 100
    quota_bytes: int = 1073741824  # 1 GB
    used_files: int = 0
    used_bytes: int = 0
    last_login: Optional[datetime] = None

    @classmethod
    async def get_by_user_id(cls, user_id: str) -> Optional["User"]:
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE user_id = $user_id LIMIT 1",
                {"user_id": user_id},
            )
            return cls(**result[0]) if result else None
        except Exception as e:
            logger.error(f"Error fetching user by user_id={user_id}: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get_by_emp_no(cls, emp_no: str) -> Optional["User"]:
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE emp_no = $emp_no LIMIT 1",
                {"emp_no": emp_no},
            )
            return cls(**result[0]) if result else None
        except Exception as e:
            logger.error(f"Error fetching user by emp_no={emp_no}: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get_all_active(cls) -> List["User"]:
        try:
            result = await repo_query(
                "SELECT * FROM user WHERE is_active = true ORDER BY emp_nm"
            )
            return [cls(**r) for r in result]
        except Exception as e:
            logger.error(f"Error fetching active users: {e}")
            raise DatabaseOperationError(e)

    def is_quota_files_ok(self) -> bool:
        return self.used_files < self.quota_files

    def is_quota_bytes_ok(self, additional_bytes: int = 0) -> bool:
        return (self.used_bytes + additional_bytes) <= self.quota_bytes

    def _prepare_save_data(self) -> dict:
        """Exclude hashed_pw from accidental overwrites unless explicitly set."""
        data = super()._prepare_save_data()
        # Remove ClassVar-like fields that shouldn't be stored
        data.pop("table_name", None)
        data.pop("nullable_fields", None)
        return data
