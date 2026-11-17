# API reference (everything goes through the gateway: `http://<gateway>:8000`)

Auth column: **public** = no token · **any** = any logged-in user · **ADMIN** / **MEMBER** = that role only · **owner/ADMIN** = the record's owner or an admin.
Send the token as `Authorization: Bearer <access_token>`. Lists are paginated with `?page=1&page_size=20`.
Each service also serves interactive docs on its own port at `/docs` (when its port is reachable).

## Registration service
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | public (`X-Admin-Key` header for `"role":"ADMIN"`) | Create an account. 409 if the email exists |
| GET | `/api/auth/check-email?email=` | public | Is the email free? |

## Login service
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | public | `{email,password}` → `{access_token, expires_in, user}` |
| GET | `/api/auth/me` | any | Current user profile |
| GET | `/api/auth/verify` | any | Validates the token, returns id + role |
| POST | `/api/auth/change-password` | any | `{current_password,new_password}` |

## Member service (Member 1)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/members?q=&role=&status=` | ADMIN | List / search accounts |
| GET | `/api/members/stats` | ADMIN | Counts by role and status |
| GET | `/api/members/{id}` | owner/ADMIN | One account |
| PUT | `/api/members/{id}` | owner/ADMIN | Update display name |
| PATCH | `/api/members/{id}/status` | ADMIN | `{"status":"ACTIVE"\|"SUSPENDED"}` |

## Catalog service (Member 1)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/books?q=&category=&author=&language=` | public | Search / browse |
| GET | `/api/books/{id}` | public | One book |
| POST | `/api/books` | ADMIN | Add book (ISBN-10/13 checksum validated, unique) |
| PUT | `/api/books/{id}` | ADMIN | Replace book details |
| DELETE | `/api/books/{id}` | ADMIN | Delete book |
| GET | `/api/categories` | public | Categories with book counts |

## Inventory service (Member 2)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/inventory/copies` | ADMIN | Register a physical copy (book must exist in Catalog) |
| GET | `/api/inventory/copies?book_id=&status=` | ADMIN | List copies |
| GET | `/api/inventory/copies/{id}` | ADMIN | One copy |
| DELETE | `/api/inventory/copies/{id}` | ADMIN | Remove a copy (409 while it is on loan) |
| PATCH | `/api/inventory/copies/{id}/status` | ADMIN | `AVAILABLE` / `BORROWED` / `LOST` / `MAINTENANCE` |
| GET | `/api/inventory/availability/{book_id}` | public | Total vs. available copies |

## Borrowing service (Member 2)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/loans` | MEMBER | `{book_id}` – borrow (account must be ACTIVE, ≤ 5 active loans, a copy must be free) |
| GET | `/api/loans/my?status=` | any | My loans |
| GET | `/api/loans?status=&user_id=&overdue=` | ADMIN | All loans |
| GET | `/api/loans/{id}` | owner/ADMIN | One loan |
| POST | `/api/loans/{id}/return` | owner/ADMIN | Return; a late return creates a fine automatically |

## Fine service (Member 3)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/fines/my?status=` | any | My fines |
| GET | `/api/fines/my/summary` | any | Unpaid / paid totals |
| GET | `/api/fines?status=&user_id=` | ADMIN | All fines |
| POST | `/api/fines` | ADMIN | Manual fine `{user_id,amount,reason}` |
| GET | `/api/fines/{id}` | owner/ADMIN | One fine with its payment receipts |
| POST | `/api/fines/{id}/pay` | owner/ADMIN | Pay: marks it PAID and creates a receipt |
| DELETE | `/api/fines/{id}` | ADMIN | Waive an unpaid fine (409 if paid) |

## Review service (Member 3)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/reviews` | MEMBER | `{book_id,rating 1-5,comment}` – one per book |
| GET | `/api/reviews?book_id=&user_id=` | public | List reviews |
| GET | `/api/reviews/summary/{book_id}` | public | Average rating + star distribution |
| PUT | `/api/reviews/{id}` | MEMBER (author) | Edit own review |
| DELETE | `/api/reviews/{id}` | author/ADMIN | Delete (admins can moderate) |

## Gateway
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Gateway status |
| GET | `/health/services` | Status of every instance of every downstream service (e.g. `catalog: up (3/3 instances)`) |
| GET | `/lb/stats` | ADMIN – requests and failures the gateway recorded per instance |

### Response headers added for traceability
| Header | Set by | Meaning |
|---|---|---|
| `X-Served-By` | each service | `<service>/<instance>` – which replica handled the request |
| `X-Upstream` | gateway | the instance URL the gateway chose |
| `X-Request-ID` | gateway | id for tracing a request (client may supply its own) |
| `X-Response-Time-ms` | each service | time spent in the service |

Anything containing `/internal` is refused by the gateway (403): those endpoints exist only for service-to-service calls.
