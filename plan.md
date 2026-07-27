# Albedo Novel Platform Plan

## Goal

Add a backend-backed editor role request flow, then introduce a Python novel microservice for
authenticated users to write novels, read novels, and manage library favorites. The Python service
must be hexagonal and deployable as AWS Lambda functions.

## Repository Setup

- Add a new repo-tool project at `novel-service`.
- Expected remote project name: `pulbhaba/albedo-novel-service.git`.
- Python packages:
  - `albedo_novels_core`: framework-free domain and application layer.
  - `albedo_novels_lambda`: AWS Lambda/API Gateway adapter layer.
- Lambda handler target: `albedo_novels_lambda.handler.lambda_handler`.

## Architecture Decisions

- Keep the existing Java auth backend as the identity and role authority.
- Send editor role requests and admin approvals to the Java auth backend, not the novel service.
- Treat `ROLE_EDITOR` as an auth-owned role. The novel service only consumes the role claim from
  validated access tokens.
- Keep auth stateless for the novel service by validating access tokens on each request.
- Do not share auth database tables with the novel service.
- Use ports in the core module for persistence, identity, clock, and ID generation.
- Put AWS-specific code in adapters only, not in domain or use cases.
- Prefer DynamoDB for the first Lambda-native persistence adapter unless relational querying becomes
  necessary.

## Phase 1: Auth Backend Editor Role Request API

Frontend currently has mock editor request and admin approval behavior. Back it with the existing
auth backend.

Endpoints to add:

- `POST /user/role-requests`
  - Authenticated user requests `ROLE_EDITOR`.
  - Body: `requestedRole`, optional `evidence`.
  - Prevent duplicate pending requests for the same user and role.
- `GET /user/role-requests/me`
  - Authenticated user reads their request history and current pending status.
- `GET /admin/promotions`
  - Admin lists role promotion requests, filterable by status.
- `POST /admin/promotions/{requestId}/approve`
  - Admin approves request and grants the role to the user.
- `POST /admin/promotions/{requestId}/reject`
  - Admin rejects request with optional reason.

Backend changes:

- Add `RolePromotionRequest` entity in `auth-data`.
- Add status enum: `PENDING`, `APPROVED`, `REJECTED`.
- Add repository methods for pending duplicate checks and admin/user listing.
- Add DTOs in `auth-client`.
- Add service methods for request, list, approve, and reject.
- Grant `UserRole(ROLE_EDITOR)` during approval inside a transaction.
- Add controller tests and service tests for duplicate pending requests, admin-only approval, role
  grant, reject, and user visibility.

## Phase 2: Novel Service Foundation

Build only the minimum service frame before adding feature behavior.

- Finalize Python version and dependency policy.
- Add JWT verification adapter:
  - Validate issuer, audience, expiry, signature, and roles claim.
  - Read auth issuer/JWKS URL/audience from environment variables.
- Add API Gateway response helpers and route dispatch.
- Add core exceptions mapped to HTTP responses.
- Add DynamoDB repository adapter behind core ports.
- Add local in-memory adapter only for tests.

Suggested environment variables:

- `AUTH_ISSUER`
- `AUTH_AUDIENCE`
- `AUTH_JWKS_URL`
- `NOVELS_TABLE_NAME`
- `CORS_ALLOWED_ORIGINS`

## Phase 3: Novel APIs

Initial authenticated API surface:

- `POST /novels`
  - Create a draft novel owned by the current user.
- `GET /novels`
  - List published novels, plus current user's drafts when requested.
- `GET /novels/{novelId}`
  - Read a published novel or an owned draft.
- `PATCH /novels/{novelId}`
  - Update owned draft metadata/content.
- `POST /novels/{novelId}/publish`
  - Requires `ROLE_EDITOR` or `ROLE_ADMIN`.
- `GET /library`
  - List current user's favorited novels.
- `PUT /library/{novelId}/favorite`
  - Add novel to current user's library.
- `DELETE /library/{novelId}/favorite`
  - Remove novel from current user's library.

Authorization rules:

- Any authenticated user can create drafts.
- Only the owner can edit a draft.
- Published novels are readable by authenticated users.
- Draft novels are readable only by owner, editor, or admin.
- Publishing requires `ROLE_EDITOR` or `ROLE_ADMIN`.
- Library favorites are private to the current user.

## Phase 4: Frontend Integration And Missing Pages

Replace mock state with API calls and add pages where the current frontend lacks a real workflow.

Existing pages to connect:

- `BooksView.vue`
  - Load published novels and user's drafts from the novel service.
  - Send editor role request to the auth backend API.
  - Show user's role request status instead of a static notice.
- `PromotionApprovalsView.vue`
  - Load requests from the auth backend `/admin/promotions` API.
  - Approve/reject using auth backend endpoints.

Pages likely needed:

- Novel reader detail page: `/books/:novelId`.
- Manuscript editor page: `/manuscripts/:novelId`.
- Library/favorites page or filter state.
- Role request status surface for non-editor users.

Frontend client work:

- Add an auth API client for role requests/promotions.
- Add a novel service API client using the same bearer token.
- Add loading, error, empty, and forbidden states.
- Keep admin routes guarded by `ROLE_ADMIN`.
- Keep publish controls guarded by `ROLE_EDITOR` or `ROLE_ADMIN`.

## Phase 5: Lambda Deployment

- Package the Lambda adapter with dependencies.
- Add infrastructure after API shape stabilizes:
  - AWS SAM, CDK, or Terraform.
  - API Gateway HTTP API.
  - DynamoDB table and IAM policy.
  - CloudWatch logs.
  - CORS configuration for the Vue frontend.
- Keep one Lambda handler initially; split by bounded context later only if cold start, IAM, or
  deployment boundaries justify it.

## Phase 6: Verification

- Auth backend:
  - Unit and controller tests for role request lifecycle.
  - JWT role claim regression test after approval.
- Novel service:
  - Core use case tests with in-memory ports.
  - Lambda adapter tests for route dispatch, auth failures, validation, and JSON responses.
  - DynamoDB adapter contract tests when persistence is added.
- Frontend:
  - Router guard checks.
  - API integration tests for role request and approval screens.
  - Manual smoke test against local auth backend and local novel Lambda adapter.

## Open Questions

- Should the novel service store full text in DynamoDB, S3, or a hybrid model with metadata in
  DynamoDB and chapter bodies in S3?
- Should publishing be immediate or require a review/submission workflow?
- Should favorites be called library items, bookmarks, or saved novels in the UI?
- Should role promotion requests support only `ROLE_EDITOR`, or a general allowlisted role set?
