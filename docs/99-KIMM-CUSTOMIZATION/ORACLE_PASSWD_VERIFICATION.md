# HR 시스템 비밀번호 검증 로직

## 개요

인사DB(Oracle VI_INF_USER_INFO)의 PWD 컬럼에 저장된 암호화된 비밀번호와 사용자 입력을 비교하는 로직입니다.

## 비밀번호 검증 프로세스

### 1단계: 사용자 입력 해싱
사용자가 입력한 비밀번호를 SHA-512로 해싱하고 Base64로 인코딩합니다.

```python
import hashlib
import base64

password = "user_input_password"
password_hash = hashlib.sha512(password.encode('utf-8')).digest()
user_hash_b64 = base64.b64encode(password_hash).decode('utf-8')
```

### 2단계: 인사DB PWD 컬럼 처리
인사DB의 PWD 컬럼 값은 특수한 인코딩이 적용되어 있어, 다음 규칙으로 처리해야 합니다:

#### 2-1. 선행 특수문자 제거
맨 앞의 `^`, `,`, `` ` `` 문자를 제거합니다.

```python
# 예: ^,`abcdefg... → abcdefg...
processed_hash = stored_hash.lstrip('^,`')
```

#### 2-2. 중괄호 치환
- `]` → `/`
- `[` → `+`

**주의**: 순서가 중요합니다. `]`를 먼저 치환한 후 `[`를 치환해야 합니다.

```python
processed_hash = processed_hash.replace(']', '/')
processed_hash = processed_hash.replace('[', '+')
```

### 3단계: 비교
처리된 해시 값과 사용자 입력 해시를 비교합니다.

```python
is_match = user_hash_b64 == processed_hash
```

## 전체 예시

```python
from app.utils.password_utils import verify_hr_password

# 사용자 입력
user_password = "MyPassword123!"

# 인사DB PWD 컬럼 값 (예시)
hr_stored = "^,`vQZAv[Q4lGOFvA0h2fkq4Bb/Jv6wF2qfRz]HQp3mM2=="

# 검증
is_valid = verify_hr_password(user_password, hr_stored)
print(f"Password valid: {is_valid}")
```

## 보안 고려사항

1. **Salt 없음**: SHA-512 해싱에 salt가 없어 Rainbow Table 공격에 취약합니다.
   - 인사 시스템의 제약사항으로 변경 불가능
   - 다른 보안 레이어(네트워크 격리, 접근 제어)로 보완 필요

2. **특수 인코딩**: 인사DB의 특수한 인코딩 방식
   - 시스템 간 호환성을 위한 레거시 방식
   - 변경 시 인사시스템 담당자와 협의 필요

3. **로그 주의**: 디버그 로그에 해시 값이 노출되지 않도록 주의
   - 프로덕션 환경에서는 로그 레벨 조정

## 트러블슈팅

### 문제: 올바른 비밀번호인데 인증 실패

1. **인사DB PWD 컬럼 값 확인**
   ```sql
   SELECT EMP_NO, PWD FROM VI_INF_USER_INFO WHERE EMP_NO = '사번';
   ```

2. **처리 전후 해시 비교**
   - `/api/auth/test-password-hash` 엔드포인트 사용
   - `user_hash_sha512_b64`와 `processed_hr_hash` 비교

3. **인코딩 문제 확인**
   - UTF-8 인코딩 확인
   - 공백/줄바꿈 문자 확인

### 문제: 특정 문자가 포함된 비밀번호 실패

- `[`, `]` 문자가 비밀번호에 포함된 경우
- 해시 후에는 문제없으나, 테스트 시 주의 필요

## 참고사항

- 인사DB 연동 시스템 업데이트 시 이 로직도 함께 검토 필요
- 암호화 방식 변경 시 마이그레이션 계획 수립 필요
- 정기적인 보안 감사 권장
