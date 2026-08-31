# Module 13: Security

> "Security is not a product, but a process." — Bruce Schneier

Security in system design is about protecting data, services, and users from threats while maintaining usability and performance. This module covers authentication, encryption, API security, and secrets management — the foundational layers every production system needs.

---

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 12 | Design Case — Payment System and E-commerce | [../12-case-payment-ecommerce/](../12-case-payment-ecommerce/) |
| **Module 13** | **Security** | **(current)** |
| Module 14 | API Design | [../14-api-design/](../14-api-design/) |

---

## Learning Objectives

By the end of this module, you will be able to:

1. **Compare** authentication mechanisms (OAuth 2.0, JWT, API keys) and choose the right one for your use case
2. **Design** authorization models (RBAC vs ABAC) and implement role-based access control
3. **Implement** encryption at rest (AES-256) and in transit (TLS 1.3) with proper key management
4. **Apply** OWASP Top 10 mitigations to protect common web application vulnerabilities
5. **Secure** APIs with rate limiting, input validation, and CORS policies
6. **Manage** secrets using environment variables vs dedicated secret managers with rotation strategies
7. **Analyze** real-world security architectures using Stripe as a case study

---

## Table of Contents

1. [Authentication & Authorization](#1-authentication--authorization) — including [Password Storage](#password-storage)
2. [Encryption](#2-encryption)
3. [OWASP Top 10](#3-owasp-top-10)
4. [API Security](#4-api-security)
5. [Secrets Management](#5-secrets-management)
6. [Case Study: Stripe Payment Security](#6-case-study-stripe-payment-security)
7. [Practice Exercise](#7-practice-exercise)
8. [Common Mistakes](#8-common-mistakes)
9. [Discussion Questions](#9-discussion-questions)
10. [Key References](#10-key-references)

---

## 1. Authentication & Authorization

### The Security Triangle

```
┌──────────────────────────────────────────────────────────────┐
│                    SECURITY TRIANGLE                         │
│                                                              │
│                     ┌─────────┐                              │
│                     │   WHO   │                              │
│                     │  (AuthN)│                              │
│                     └────┬────┘                              │
│                          │                                   │
│              ┌───────────┴───────────┐                       │
│              │                       │                       │
│         ┌────┴────┐            ┌─────┴─────┐                 │
│         │  WHAT   │            │  HOW      │                 │
│         │ (AuthZ) │            │(Transport)│                 │
│         └─────────┘            └───────────┘                 │
│                                                              │
│   Authentication: Prove you are who you claim to be          │
│   Authorization:  What are you allowed to do?                │
│   Transport:      How is data protected in transit?          │
└──────────────────────────────────────────────────────────────┘
```

### Authentication Mechanisms Comparison

| Mechanism | Use Case | Stateless | Token Lifetime | Complexity |
|-----------|----------|-----------|----------------|------------|
| **API Keys** | Service-to-service, simple integrations | Yes | Long-lived (months/years) | Low |
| **JWT (Bearer)** | Web apps, mobile apps, SPAs | Yes | Short-lived (15min-1hr) | Medium |
| **OAuth 2.0** | Third-party access, delegated auth | Varies | Access: short, Refresh: long | High |
| **Session Cookies** | Traditional web apps | No (server state) | Until expiry/logout | Low |
| **mTLS** | Service mesh, high-security APIs | N/A (cert-based) | Certificate validity | High |

### Password Storage

Before any of the mechanisms above matter, you have to store the credential
that bootstraps them. This is the single most commonly botched piece of
application security, and the failure mode is catastrophic and delayed: a
database leaks today, and the passwords are cracked at leisure, offline,
for years afterward.

**The rule: never store a password you can read.** Not encrypted — encrypted
implies a key that decrypts it, and whoever took your database probably took
your key too. Store a *slow, salted hash* and compare hashes at login.

```
  WRONG                          STILL WRONG                  RIGHT
  ─────                          ───────────                  ─────
  store "hunter2"                store SHA256("hunter2")      store
                                                              argon2id(
  Leak = instant total loss      SHA-256 is designed to be      "hunter2",
                                 FAST. A commodity GPU tries    salt,
                                 billions/sec against a         cost params
                                 precomputed rainbow table.   )
                                 Unsalted = identical
                                 passwords hash identically.  Leak = attacker
                                                              must spend real
                                                              money per
                                                              password.
```

General-purpose hashes (MD5, SHA-1, SHA-256) are the wrong tool here for
exactly the reason they are the right tool elsewhere: they are fast. Password
hashing wants a function that is *deliberately expensive* and tunable, so you
can raise the cost as hardware improves.

| Algorithm | Verdict | Notes |
|-----------|---------|-------|
| **Argon2id** | Preferred | Memory-hard — resists GPU and ASIC cracking. OWASP's first recommendation |
| **scrypt** | Good | Also memory-hard; a reasonable choice where Argon2 isn't available |
| **bcrypt** | Acceptable | Long-serving and battle-tested, but only CPU-hard. Note its 72-byte input truncation |
| **PBKDF2** | Use only if required | FIPS-compliant, but not memory-hard — needs a very high iteration count |
| **SHA-256 / MD5 / SHA-1** | Never | Fast by design; unsalted variants fall to rainbow tables instantly |

Three details that are easy to miss:

- **The salt is per-user, random, and not a secret.** It is stored alongside
  the hash. Its only job is to make two identical passwords hash differently,
  which defeats precomputed rainbow tables. Every mainstream library
  generates and embeds it for you — do not invent your own scheme.
- **Compare in constant time.** A naive `==` on hash strings returns faster
  on an early-mismatch, which leaks information over enough samples. Use the
  library's verify function, not a string comparison.
- **Cost parameters are a living setting.** A work factor chosen in 2018 is
  cheap to crack now. Record the parameters with each hash so you can
  transparently re-hash on next successful login as you raise them.

```python
# The entire correct implementation, using a maintained library.
# Note that there is no separate salt argument and no manual comparison:
# the library generates the salt, embeds it plus the cost parameters in
# the output string, and verifies in constant time.
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

ph = PasswordHasher()  # OWASP-aligned defaults; tune for your hardware


def register(password: str) -> str:
    """Return the value to store. Never store the password itself."""
    return ph.hash(password)


def login(stored_hash: str, password: str) -> tuple[bool, str | None]:
    """Return (authenticated, new_hash_to_persist_or_None)."""
    try:
        ph.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False, None
    # Cost parameters were raised since this hash was written — upgrade it
    # now, while we legitimately hold the plaintext.
    if ph.check_needs_rehash(stored_hash):
        return True, ph.hash(password)
    return True, None
```

> **Do not hand-roll this.** Every line you write here is a line that can
> silently disable the protection — a reused salt, a truncated input, a
> timing leak. Use the platform's password-hashing library and spend your
> attention on rate limiting the login endpoint (see Common Mistakes) and on
> supporting a second factor, which protects users whose passwords were
> already leaked somewhere else.

### OAuth 2.0 Flow

```
┌──────────┐                              ┌──────────────┐
│  Client   │──(1) Authorization Request──▶│  Auth Server  │
│  (App)    │                              │  (e.g. Okta)  │
└─────┬─────┘                              └───────┬───────┘
      │                                            │
      │    (2) User authenticates                  │
      │    (3) Authorization grant                 │
      │◀───────────────────────────────────────────│
      │                                            │
      │──(4) Exchange grant for tokens────────────▶│
      │◀──(5) Access Token + Refresh Token────────│
      │                                            │
      │──(6) API call with Access Token────────────▶┌──────────────┐
      │◀──(7) Protected Resource───────────────────│  Resource     │
      │                                            │  Server       │
      └────────────────────────────────────────────└──────────────┘
```

### JWT Structure

```python
import jwt
import datetime
from typing import Optional

class JWTManager:
    """Demonstrates JWT creation and validation."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = "HS256"
    
    def create_token(
        self,
        user_id: str,
        roles: list[str],
        expires_in_minutes: int = 15
    ) -> str:
        # UTC, always. `datetime.now()` without a timezone is interpreted as
        # UTC by PyJWT regardless of the server's actual offset, so a host in
        # UTC+7 would issue tokens that expired 7 hours ago.
        now = datetime.datetime.now(datetime.timezone.utc)

        payload = {
            "sub": user_id,                           # Subject (who)
            "roles": roles,                           # Claims (what they can do)
            "iat": now,                               # Issued at
            "exp": now + datetime.timedelta(minutes=expires_in_minutes),
            "iss": "auth.example.com",                # Issuer
            "aud": "api.example.com",                 # Intended audience
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            return jwt.decode(
                token,
                self.secret_key,
                # Pin the algorithm list. Accepting whatever the token's
                # header claims is the classic JWT vulnerability: an attacker
                # sets alg=none, or swaps RS256 for HS256 and signs with the
                # public key as the HMAC secret.
                algorithms=[self.algorithm],
                audience="api.example.com",
                issuer="auth.example.com",
            )
        except jwt.ExpiredSignatureError:
            return None  # Token expired
        except jwt.InvalidTokenError:
            return None  # Bad signature, wrong aud/iss, malformed, etc.

# Usage
manager = JWTManager("your-secret-key-change-in-production")
token = manager.create_token(user_id="user_123", roles=["admin", "reader"])
print(f"Token: {token[:50]}...")

payload = manager.verify_token(token)
print(f"Valid payload: {payload}")
```

### RBAC vs ABAC

```
┌────────────────────────────────────────────────────────────────┐
│  RBAC (Role-Based Access Control)                              │
│                                                                │
│  User ──▶ Role ──▶ Permission                                  │
│                                                                │
│  user_1 ──▶ admin ──▶ {read, write, delete, manage_users}      │
│  user_2 ──▶ editor ──▶ {read, write}                           │
│  user_3 ──▶ viewer ──▶ {read}                                  │
│                                                                │
│  ✓ Simple to understand and audit                              │
│  ✓ Works well for hierarchical organizations                   │
│  ✗ Role explosion (too many roles for fine-grained control)    │
├────────────────────────────────────────────────────────────────┤
│  ABAC (Attribute-Based Access Control)                         │
│                                                                │
│  Subject Attributes + Resource Attributes + Environment        │
│                              ↓                                 │
│                         Policy Engine                          │
│                              ↓                                 │
│                          Decision                              │
│                                                                │
│  Example:                                                      │
│  IF user.department == "finance"                               │
│  AND resource.classification == "confidential"                 │
│  AND time.hour BETWEEN 9 AND 17                                │
│  AND location.country == "US"                                  │
│  THEN ALLOW                                                    │
│                                                                │
│  ✓ Fine-grained, context-aware                                 │
│  ✓ Scales without role explosion                               │
│  ✗ Complex to implement and audit                              │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Encryption

### Encryption at Rest vs In Transit

| Aspect | At Rest | In Transit |
|--------|---------|------------|
| **Protects against** | Physical theft, disk compromise | Network sniffing, MITM attacks |
| **Common algorithms** | AES-256-GCM, ChaCha20 | TLS 1.3, AES-256-GCM |
| **Key management** | KMS, HSM, vault | Certificate authorities, Let's Encrypt |
| **Performance impact** | Minimal (modern CPUs have AES-NI) | Minimal (TLS 1.3 is fast) |
| **Implementation** | Database/OS level | Network/protocol level |

### AES-256 Encryption Example

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class EncryptionService:
    """Demonstrates AES-256-GCM encryption."""
    
    def __init__(self):
        # In production, fetch from KMS
        self.key = AESGCM.generate_key(bit_length=256)
    
    def encrypt(self, plaintext: str, associated_data: str = None) -> dict:
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(self.key)
        
        ciphertext = aesgcm.encrypt(
            nonce,
            plaintext.encode('utf-8'),
            associated_data.encode('utf-8') if associated_data else None
        )
        
        return {
            "ciphertext": ciphertext.hex(),
            "nonce": nonce.hex()
        }
    
    def decrypt(self, ciphertext_hex: str, nonce_hex: str, 
                associated_data: str = None) -> str:
        ciphertext = bytes.fromhex(ciphertext_hex)
        nonce = bytes.fromhex(nonce_hex)
        aesgcm = AESGCM(self.key)
        
        plaintext = aesgcm.decrypt(
            nonce,
            ciphertext,
            associated_data.encode('utf-8') if associated_data else None
        )
        
        return plaintext.decode('utf-8')

# Usage
service = EncryptionService()
encrypted = service.encrypt("Sensitive data: SSN 123-45-6789", 
                           associated_data="user_id:123")
print(f"Encrypted: {encrypted}")

decrypted = service.decrypt(
    encrypted["ciphertext"], 
    encrypted["nonce"],
    associated_data="user_id:123"
)
print(f"Decrypted: {decrypted}")
```

### Key Management with KMS

```
┌───────────────────────────────────────────────────────────────────┐
│                    KMS Key Hierarchy                              │
│                                                                   │
│                   ┌─────────────────┐                             │
│                   │   Master Key    │                             │
│                   │ (HSM-protected, │                             │
│                   │  never exported)│                             │
│                   └────────┬────────┘                             │
│                            │ wraps / unwraps                      │
│           ┌────────────────┼────────────────┐                     │
│           │                │                │                     │
│     ┌─────▼──────┐  ┌──────▼─────┐  ┌───────▼────┐                │
│     │    DEK     │  │    DEK     │  │    DEK     │                │
│     │  (database)│  │   (files)  │  │   (logs)   │                │
│     └─────┬──────┘  └──────┬─────┘  └───────┬────┘                │
│           │ encrypts       │                │                     │
│           ▼                ▼                ▼                     │
│      table rows        object blobs     log records               │
│                                                                   │
│   DEK = Data Encryption Key. The master key never touches your    │
│   data — it only encrypts the DEKs, which are stored alongside    │
│   the ciphertext in wrapped form. This is "envelope encryption",  │
│   and it is why rotating the master key does not require          │
│   re-encrypting terabytes: you re-wrap the DEKs only.             │
│                                                                   │
│   Key Rotation Schedule:                                          │
│   - Master Key: 1-2 years                                         │
│   - DEKs: 90 days (or per compliance requirement)                 │
│   - TLS certificates: 90 days (Let's Encrypt auto-renew)          │
└───────────────────────────────────────────────────────────────────┘
```

### TLS 1.3 Handshake (Simplified)

```
Client                                          Server
  │                                                │
  │──(1) ClientHello──────────────────────────────▶│
  │    - Supported ciphers                         │
  │    - Key share (ECDHE)                         │
  │    - SNI (Server Name Indication)              │
  │                                                │
  │◀──(2) ServerHello─────────────────────────────│
  │    - Selected cipher                           │
  │    - Key share (ECDHE)                         │
  │    - Certificate                               │
  │    - CertificateVerify                         │
  │    - Finished                                  │
  │                                                │
  │──(3) Finished─────────────────────────────────▶│
  │                                                │
  │◀══════(4) Encrypted Application Data══════════│
  │                                                │
  
  Key difference from TLS 1.2: Only 1 round trip (vs 2)
  All handshake messages after ServerHello are encrypted
```

---

## 3. OWASP Top 10

The OWASP Top 10 (2021) represents the most critical web application security risks:

```
┌────┬─────────────────────────────────────┬──────────────────────────┐
│ #  │ Risk                                │ Mitigation Summary       │
├────┼─────────────────────────────────────┼──────────────────────────┤
│ A01│ Broken Access Control               │ RBAC, deny by default    │
│ A02│ Cryptographic Failures              │ Encrypt, use strong alg  │
│ A03│ Injection                           │ Parameterized queries    │
│ A04│ Insecure Design                     │ Threat modeling          │
│ A05│ Security Misconfiguration           │ Hardening, least priv    │
│ A06│ Vulnerable Components               │ Dependency scanning      │
│ A07│ Authentication Failures             │ MFA, rate limiting       │
│ A08│ Software & Data Integrity Failures  │ Signed builds, SRI       │
│ A09│ Security Logging Failures           │ Centralized logging      │
│ A10│ Server-Side Request Forgery         │ Validate URLs, allowlist │
└────┴─────────────────────────────────────┴──────────────────────────┘
```

### Injection Prevention Example

```python
# VULNERABLE: SQL Injection
def get_user_vulnerable(user_id: str):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    # Attacker input: "'; DROP TABLE users; --"
    return db.execute(query)

# SECURE: Parameterized Query
def get_user_secure(user_id: str):
    query = "SELECT * FROM users WHERE id = %s"
    return db.execute(query, (user_id,))

# SECURE: ORM (SQLAlchemy style)
def get_user_orm(user_id: str):
    return User.query.filter(User.id == user_id).first()
```

### Input Validation

```python
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator

class CreateUserRequest(BaseModel):
    """Pydantic v2. Note the API differences from v1:
       @validator  → @field_validator (+ @classmethod)
       regex=      → pattern=
    Mixing the two generations in one model is a common source of
    validators that silently never run.
    """

    username: Annotated[str, Field(
        min_length=3,
        max_length=32,
        pattern=r'^[a-zA-Z0-9_]+$',
    )]
    # Prefer the library's validated type over a hand-rolled regex —
    # email grammar (RFC 5322) is far more permissive than it looks, and
    # homegrown patterns reject valid addresses.
    email: EmailStr
    age: Annotated[int, Field(ge=0, le=150)]

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: str) -> str:
        # Store a canonical form so lookups and uniqueness checks agree.
        return v.strip().lower()

# Pydantic rejects invalid input at the boundary, so business logic
# downstream can assume these invariants already hold.
```

**Validate at the edge, but never *only* at the edge.** Input validation is a
data-quality control, not a security boundary on its own:

| Layer | What it catches |
|-------|-----------------|
| Schema validation (above) | Malformed, out-of-range, wrong-type input |
| Parameterized queries | SQL injection — regardless of what got through |
| Output encoding | XSS — regardless of what got stored |
| Authorization check | Whether *this* caller may act on *this* record |

A username that passes `^[a-zA-Z0-9_]+$` is still dangerous if you interpolate
it into SQL. Allowlists reduce attack surface; they do not replace the defence
at the point of use.

---

## 4. API Security

### Rate Limiting Strategies

```
┌─────────────────────────────────────────────────────────────────┐
│  Strategy         │  Implementation      │  Use Case            │
├───────────────────┼──────────────────────┼───────────────────── ┤
│  Fixed Window     │  Counter per hour    │  Simple APIs         │
│  Sliding Window   │  Timestamps per min  │  Smooth traffic      │
│  Token Bucket     │  Tokens + refill     │  Bursty traffic      │
│  Leaky Bucket     │  Queue + fixed rate  │  Constant output     │
└─────────────────────────────────────────────────────────────────┘
```

```python
import time
from collections import defaultdict
from functools import wraps

class SlidingWindowRateLimiter:
    """Sliding window rate limiter using Redis-style storage."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
    
    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        
        # Remove expired requests
        self.requests[key] = [
            ts for ts in self.requests[key] if ts > window_start
        ]
        
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        self.requests[key].append(now)
        return True

# Usage
limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60)

def rate_limit(func):
    @wraps(func)
    def wrapper(request_key: str, *args, **kwargs):
        if not limiter.is_allowed(request_key):
            raise Exception("Rate limit exceeded")
        return func(request_key, *args, **kwargs)
    return wrapper
```

### CORS Configuration

```python
# FastAPI example with CORS middleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# PRODUCTION: Explicit origins only
ALLOWED_ORIGINS = [
    "https://app.yourcompany.com",
    "https://admin.yourcompany.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # Never use "*" in production
    allow_credentials=True,           # Allow cookies/auth headers
    allow_methods=["GET", "POST"],    # Only needed methods
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,                      # Cache preflight for 10 min
)
```

### Security Headers

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'; script-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

---

## 5. Secrets Management

### Environment Variables vs Secret Managers

| Aspect | Environment Variables | Secret Managers (Vault, AWS SM) |
|--------|----------------------|--------------------------------|
| **Security** | Basic (visible in process) | Strong (encrypted, access logged) |
| **Rotation** | Manual, requires restart | Automatic, seamless |
| **Access Control** | OS-level only | Fine-grained IAM policies |
| **Audit Trail** | None built-in | Full audit logging |
| **Complexity** | Very simple | Moderate to high |
| **Cost** | Free | $0.40-$0.60 per secret/month |
| **Best For** | Dev, simple apps | Production, compliance |

### Secret Rotation Pattern

```python
import hashlib
import time
from typing import Optional

class SecretRotator:
    """Demonstrates zero-downtime secret rotation."""
    
    def __init__(self):
        self.current_secret: Optional[str] = None
        self.previous_secret: Optional[str] = None
        self.rotation_time: float = 0
        self.rotation_interval: int = 3600 * 24 * 90  # 90 days
    
    def get_current_secret(self) -> str:
        if self.current_secret is None:
            self.rotate()
        return self.current_secret
    
    def rotate(self):
        import secrets
        new_secret = secrets.token_hex(32)
        
        if self.current_secret:
            self.previous_secret = self.current_secret
        
        self.current_secret = new_secret
        self.rotation_time = time.time()
        
        # In production: Update secret manager, not in-memory
        # await secret_manager.put("api_key", new_secret)
    
    def verify_secret(self, provided_secret: str) -> bool:
        """Accept both current and previous during grace period."""
        if provided_secret == self.current_secret:
            return True
        
        # Grace period: accept old secret for 1 hour after rotation
        if (self.previous_secret and 
            provided_secret == self.previous_secret and
            time.time() - self.rotation_time < 3600):
            return True
        
        return False

# Usage
rotator = SecretRotator()
rotator.rotate()
print(f"Current secret: {rotator.get_current_secret()[:20]}...")
```

---

## 6. Case Study: Stripe Payment Security

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      STRIPE SECURITY LAYERS                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │   Client    │    │   Client    │    │   Client    │              │
│  │  (Browser)  │    │  (Mobile)   │    │  (Server)   │              │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘              │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            │                                        │
│                    ┌───────┴───────┐                                │
│                    │  TLS 1.3 +    │                                │
│                    │  Certificate  │                                │
│                    │  Pinning      │                                │
│                    └───────┬───────┘                                │
│                            │                                        │
│              ┌─────────────┴─────────────┐                          │
│              │   Rate Limiting + WAF     │                          │
│              │   (DDoS protection)       │                          │
│              └─────────────┬─────────────┘                          │
│                            │                                        │
│         ┌──────────────────┼──────────────────┐                     │
│         │                  │                  │                     │
│   ┌─────▼─────┐      ┌─────▼─────┐      ┌─────▼─────┐               │
│   │   AuthN   │      │   AuthZ   │      │  PCI DSS  │               │
│   │  Service  │      │  Service  │      │   Vault   │               │
│   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘               │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            │                                        │
│                    ┌───────┴───────┐                                │
│                    │  Encrypted    │                                │
│                    │  Data Store   │                                │
│                    │  (AES-256)    │                                │
│                    └───────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Security Practices

**1. API Key Design**
- `sk_live_` prefix for secret keys (server-side only)
- `pk_live_` prefix for publishable keys (client-side)
- Keys are scoped to specific resources
- Automatic key rotation with zero downtime

**2. Idempotency for Safety**
```python
import uuid

def create_payment_stripe_style(amount: int, idempotency_key: str = None):
    """
    Stripe's approach: Every write operation is idempotent.
    Client provides a unique key; server deduplicates.
    """
    if idempotency_key is None:
        idempotency_key = str(uuid.uuid4())
    
    # Check if this idempotency key was already processed
    existing = db.get_idempotency(idempotency_key)
    if existing:
        return existing["response"]  # Return cached response
    
    # Process payment
    result = process_payment(amount)
    
    # Store result for future idempotent requests
    db.store_idempotency(idempotency_key, result)
    
    return result
```

**3. Webhook Signature Verification**
```python
import hashlib
import hmac
import time

def verify_webhook_signature(payload: bytes, header: str,
                             secret: str, tolerance: int = 300) -> bool:
    """Verify a Stripe-style webhook signature.

    The header looks like:  t=1690000000,v1=5257a8...,v1=<older key>

    Three things must all hold, and skipping any one of them defeats the
    mechanism:
      1. The signature covers the timestamp AND the body ("t.payload"),
         not the body alone — otherwise a captured request replays forever.
      2. The timestamp is inside the tolerance window.
      3. The comparison is constant-time.
    """
    parts = dict(
        kv.split("=", 1) for kv in header.split(",") if "=" in kv
    )
    timestamp = parts.get("t")
    if timestamp is None:
        return False

    # (2) Reject stale deliveries — this is the replay defence, and it only
    # works because the timestamp is inside the signed material below.
    if abs(time.time() - int(timestamp)) > tolerance:
        return False

    # (1) Sign the timestamp and body together, exactly as the sender did.
    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    # (3) Accept if ANY provided v1 matches — this is what lets you rotate
    # the signing secret without dropping in-flight webhooks.
    provided = [v for k, v in parts.items() if k == "v1"]
    return any(hmac.compare_digest(expected, sig) for sig in provided)
```

> **Why `hmac.compare_digest` and not `==`?** String equality short-circuits on
> the first differing byte, so response time leaks how many leading bytes were
> correct. An attacker can recover a signature byte by byte from timing alone.
>
> **Why sign the timestamp?** If the HMAC covers only the body, a valid request
> captured off the wire stays valid indefinitely — a `tolerance` check on an
> *unsigned* timestamp is worthless, because the attacker just edits it.
>
> Note that `parts` above keeps only the last `v1` when several are present.
> Real implementations parse the header into a list of `(scheme, signature)`
> pairs so every candidate key is checked; the dict form is shown for brevity.

### PCI DSS Compliance

```
┌────────────────────────────────────────────────────────────────┐
│  PCI DSS Requirements for Stripe Integration                   │
├────────────────────────────────────────────────────────────────┤
│  1. Never store raw card numbers (use tokens)                  │
│  2. Use Stripe.js/Elements (card data never hits your server)  │
│  3. Validate webhook signatures                                │
│  4. Use TLS for all communications                             │
│  5. Implement access controls (least privilege)                │
│  6. Log and monitor all access to cardholder data              │
│  7. Regular security testing and penetration testing           │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Practice Exercise

### Design a Secure File Upload Service

**Requirements:**
- Users can upload files up to 10MB
- Only authenticated users can upload
- Files are scanned for malware before storage
- Files are encrypted at rest
- Files are served via signed URLs (expire in 1 hour)

**Deliverables:**
1. Architecture diagram showing security layers
2. API design with authentication and authorization
3. Encryption strategy for files at rest
4. Implementation of signed URL generation
5. Rate limiting strategy

**Starter Code:**
```python
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

class SecureFileService:
    def __init__(self, encryption_key: str, signing_key: str):
        self.encryption_key = encryption_key
        self.signing_key = signing_key
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.allowed_content_types = [
            'image/jpeg', 'image/png', 'application/pdf',
            'text/plain', 'application/json'
        ]
    
    def generate_signed_url(self, file_path: str, 
                           expires_in_minutes: int = 60) -> str:
        """Generate a signed URL for secure file access."""
        # TODO: Implement
        # Include expiry timestamp in signature
        # Return URL with signature and expiry
        pass
    
    def validate_upload(self, content_type: str, file_size: int) -> bool:
        """Validate file upload meets security requirements."""
        # TODO: Implement
        # Check content type against allowlist
        # Check file size against limit
        pass
```

**Expected Security Layers:**
```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Authentication (JWT verification)         │
│  Layer 2: Authorization (user can upload to target) │
│  Layer 3: Input Validation (type, size, malware)    │
│  Layer 4: Encryption (AES-256 at rest)              │
│  Layer 5: Access Control (signed URLs)              │
│  Layer 6: Rate Limiting (per user, per IP)          │
│  Layer 7: Audit Logging (all operations)            │
└─────────────────────────────────────────────────────┘
```

---

## 8. Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Hardcoding secrets in code** | Secrets leak in version control | Use environment variables or secret managers |
| **No token expiry** | Stolen tokens work forever | Set short expiry (15-60 min) + refresh tokens |
| **Ignoring OWASP Top 10** | Common attacks are well-known | Review OWASP checklist for every API |
| **No rate limiting on auth endpoints** | Brute force attacks succeed | Rate limit login, password reset, API key creation |
| **Encrypting only in transit** | Data at rest is vulnerable | Encrypt sensitive data at rest too |
| **No secret rotation** | Compromised secrets stay valid forever | Rotate secrets periodically (90 days) |
| **Hashing passwords with SHA-256** | It's fast by design — a GPU tries billions of guesses per second against a stolen table | Use Argon2id (or bcrypt/scrypt); the slowness is the security property |
| **Encrypting passwords instead of hashing them** | Encryption is reversible, and the attacker who took your database usually took the key too | Store a one-way salted hash; you never need to read a password back |
| **Comparing hashes with `==`** | Early-mismatch return leaks timing information across enough attempts | Use the library's constant-time verify function |

---

## 9. Discussion Questions

### Question 1: JWT vs Sessions

**Question:** When would you choose JWT over server-side sessions, and vice versa?

**Model Answer:**
- **Choose JWT when:** You have distributed systems (multiple servers), need stateless authentication, or are building APIs for mobile/SPA clients. JWTs scale horizontally without shared session storage.
- **Choose Sessions when:** You need immediate session invalidation (e.g., logout), have a monolithic app, or require server-side control over session state. Sessions are simpler to debug and revoke.
- **Hybrid approach:** Use short-lived JWTs (15 min) with refresh tokens stored server-side. This gives you stateless fast-path with revocation capability.

### Question 2: Encryption Overhead

**Question:** What's the performance impact of encrypting all database fields, and when is it worth it?

**Model Answer:**
- **Performance:** AES-256 with hardware acceleration (AES-NI) adds <1% overhead for most workloads. The bigger cost is key management complexity.
- **Worth it when:** Regulatory compliance (GDPR, HIPAA, PCI DSS), protecting PII/PHI, or threat model includes physical disk access.
- **Not worth it when:** Data is non-sensitive, performance is critical and hardware lacks AES-NI, or the data is already encrypted at rest at the disk/volume level.
- **Best practice:** Encrypt sensitive fields (SSN, credit cards, health data) even if full-disk encryption exists — defense in depth.

### Question 3: Rate Limiting Strategy

**Question:** Your API serves both human users (100 req/min) and service accounts (10000 req/min). How do you design rate limiting?

**Model Answer:**
- **Tiered rate limits:** Different limits per client type based on API key metadata.
- **Token bucket algorithm:** Allows bursts while maintaining average rate.
- **Redis-backed counters:** For distributed rate limiting across multiple API servers.
- **Graceful degradation:** Return `429 Too Many Requests` with `Retry-After` header, don't just drop connections.
- **Monitoring:** Track rate limit hits to identify abuse patterns and adjust limits.

### Question 4: Secrets Rotation

**Question:** How do you rotate a database password without downtime?

**Model Answer:**
1. Add new password to secret manager alongside old one
2. Update application to accept both passwords (dual-write mode)
3. Update all application instances to new password
4. Verify all traffic uses new password via logs
5. Remove old password from secret manager
6. Update connection pools to use only new password

**Key insight:** The "overlap period" is crucial — never switch atomically without a grace period.

---

## 10. Key References

### Official Documentation
- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749) - OAuth 2.0 authorization framework
- [JWT RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519) - JSON Web Token specification
- [OWASP Top 10 2021](https://owasp.org/Top10/) - Web application security risks
- [NIST SP 800-57](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final) - Key management recommendations

### Books & Courses
- *Web Application Security* by Andrew Hoffman
- *Cryptography Engineering* by Ferguson, Schneier, and Kohno
- *The Web Application Hacker's Handbook* by Stuttard and Pinto
- [Google's Security Best Practices](https://cloud.google.com/docs/security/best-practices)

### Tools & Libraries
- [OWASP ZAP](https://www.zaproxy.org/) - Security testing proxy
- [Bandit](https://bandit.readthedocs.io/) - Python security linter
- [Semgrep](https://semgrep.dev/) - Static analysis for security
- [Vault](https://www.vaultproject.io/) - Secrets management by HashiCorp

### Real-World Implementations
- [Stripe Security Documentation](https://stripe.com/docs/security) - Payment security architecture
- [GitHub's Token Scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps) - Fine-grained API access control
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html) - Identity and access management

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 04: Load Balancing](../04-load-balancing/README.md) | Security considerations for distributed load balancers (SSL termination, health check security) |
| [Module 07: Reliability](../07-reliability/README.md) | Security as a component of system reliability (DDoS mitigation, failover strategies) |
| [Module 22: Production AI](../22-production-ai-system/README.md) | Securing ML pipelines, model access control, and data privacy in production AI systems |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│                    Security — Key Takeaways                    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Authentication proves identity; authorization decides what │
│     an authenticated identity can do — never conflate the two  │
│  2. Store passwords as slow, salted hashes (Argon2id) — never  │
│     encrypted, and never with a fast hash like SHA-256; the    │
│     slowness is the entire security property                   │
│  3. Prefer short-lived, signed tokens (JWT with a real expiry) │
│     over long-lived API keys wherever the client can support   │
│     the handshake                                              │
│  4. Encrypt at rest AND in transit — one without the other     │
│     leaves an obvious gap                                      │
│  5. Envelope encryption (DEK wrapped by a KMS-held key) beats a│
│     single hardcoded encryption key for anything that needs    │
│     rotation                                                   │
│  6. Validate and sanitize every external input — OWASP's Top 10│
│     exists because the same mistakes recur across decades of   │
│     applications                                               │
│  7. Rate limit and scope API keys per client, not just globally│
│     — one noisy or compromised client shouldn't degrade        │
│     everyone else                                              │
│  8. Never store secrets in code or config files — use a        │
│     dedicated secrets manager with rotation, not environment   │
│     variables as a permanent home                              │
│  9. Treat security as a process with ongoing audits, not a     │
│     checklist you complete once and forget                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 12: Design Case — Payment System and E-commerce](../12-case-payment-ecommerce/README.md)

**Next:** [Module 14: API Design](../14-api-design/README.md)

---

*Module 13 of 22 in the System Design Playground*
