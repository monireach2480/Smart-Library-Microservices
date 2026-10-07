# Authentication, API Gateway and role-based access control

## Roles
| Role | Who | Created by |
|---|---|---|
| `MEMBER` | library patron | public sign-up (`POST /api/auth/register`) |
| `ADMIN` | librarian | sign-up with the secret `X-Admin-Key` header (value = `ADMIN_REGISTRATION_KEY`, known only to the team) |

## JWT
* The **Login service** verifies the email/password (Argon2id hash) and signs a JWT (**HS256**, `SECRET_KEY` ≥ 32 chars, valid 60 min).
* Claims: `sub` (user id), `role`, `email`, `name`, `type=access`, `iat`, `exp`, `jti`.
* Verification always pins the algorithm list, requires `exp/sub/iat`, and rejects tokens that are not `type=access`.
* Suspended accounts cannot log in (403) and cannot borrow, even with an old token.

## Two layers of enforcement
```
Client ──► API Gateway ───────────────► Microservice
           1. token present & valid?     3. token valid? (re-checked)
           2. route allowed for role?    4. role / ownership allowed?
           401 / 403 before forwarding   401 / 403 from the service itself
```
* The **gateway** validates the token *before* forwarding and applies the coarse rules (public / any logged-in user / ADMIN-only). Anything containing `/internal` is refused (403).
* Each **service** verifies the token again and applies the fine rules (MEMBER-only, owner-or-admin). Calling a service port directly therefore gives the same 401/403 – tested in the evidence run.
* **Service-to-service** endpoints (`/internal/...`) need the shared `X-Internal-Key` and are not reachable through the gateway.

## Permission matrix
✔ allowed · ✘ refused (401 if not logged in, otherwise 403) · own = only the user's own records

| Action | Public | MEMBER | ADMIN |
|---|:-:|:-:|:-:|
| Register / log in / check e-mail | ✔ | ✔ | ✔ |
| Create an ADMIN account | needs `X-Admin-Key` | needs key | needs key |
| Browse & search books, categories, availability, reviews | ✔ | ✔ | ✔ |
| Add / edit / delete books | ✘ | ✘ | ✔ |
| Add / list / change / delete book copies | ✘ | ✘ | ✔ |
| List & search members, stats, suspend / re-activate | ✘ | ✘ | ✔ |
| View / rename a member record | ✘ | own | any |
| Borrow a book | ✘ | ✔ | ✘ (403) |
| Return a book / view a loan | ✘ | own | any |
| List all loans, overdue loans | ✘ | ✘ | ✔ |
| View my loans / fines | ✘ | ✔ | ✔ |
| Pay a fine | ✘ | own | any (desk) |
| List all fines, create or waive a fine | ✘ | ✘ | ✔ |
| Write a review | ✘ | ✔ | ✘ (403) |
| Edit a review | ✘ | own | ✘ |
| Delete a review | ✘ | own | any (moderation) |
| Gateway load-balancer stats (`/lb/stats`) | ✘ | ✘ | ✔ |
| `/internal/*` endpoints | ✘ | ✘ | ✘ (403 via gateway) |

## Other protections
* Passwords: Argon2id; login does the same hashing work for unknown e-mails (no user enumeration by timing); rules ≥ 8 chars with a letter and a digit.
* Parameterised queries via SQLAlchemy (no SQL injection); strict request validation (Pydantic).
* Containers run as a non-root user; PostgreSQL is on a separate Docker network and its port is not published; on EC2 only port 8000 is open to the internet.
* Secrets only in `.env` files (git-ignored), never in the repository.
* `X-Internal-Key` is stripped from incoming client requests by the gateway.

## Demonstrating it (Postman folders 1–2 and the "expect 401/403" requests)
`No token → 401` · `garbage token → 401` · `MEMBER lists members → 403` · `MEMBER adds a book → 403` · `ADMIN borrows → 403` · `internal endpoint via gateway → 403` · `suspended user logs in → 403`.
