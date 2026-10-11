# PostgreSQL `neon_auth` schema

**Role:** Provider-managed authentication. Observed Neon Auth identity, credential, organization and verification metadata.

**Access family:** No checked-in MathBank REST consumer found. Current learner JWT/shared admin login does not thereby use Neon Auth.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `neon_auth.account`

**Kind / use case:** table. Provider/credential account linkage; secret values not inspected.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `accountId` | `text` | no | `-` | `- / -` |
| `providerId` | `text` | no | `-` | `- / -` |
| `userId` | `uuid` | no | `-` | `- / -` |
| `accessToken` | `text` | yes | `-` | `- / -` |
| `refreshToken` | `text` | yes | `-` | `- / -` |
| `idToken` | `text` | yes | `-` | `- / -` |
| `accessTokenExpiresAt` | `timestamp with time zone` | yes | `-` | `- / -` |
| `refreshTokenExpiresAt` | `timestamp with time zone` | yes | `-` | `- / -` |
| `scope` | `text` | yes | `-` | `- / -` |
| `password` | `text` | yes | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `updatedAt` | `timestamp with time zone` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `account_accountId_not_null` / `n` | `NOT NULL "accountId"` | deferrable=False, initially deferred=False, validated=True |
| `account_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `account_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `account_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `account_providerId_not_null` / `n` | `NOT NULL "providerId"` | deferrable=False, initially deferred=False, validated=True |
| `account_updatedAt_not_null` / `n` | `NOT NULL "updatedAt"` | deferrable=False, initially deferred=False, validated=True |
| `account_userId_fkey` / `f` | `FOREIGN KEY ("userId") REFERENCES neon_auth."user"(id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `account_userId_not_null` / `n` | `NOT NULL "userId"` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `account_pkey`: `CREATE UNIQUE INDEX account_pkey ON neon_auth.account USING btree (id)`; valid=True, ready=True.
- `account_userId_idx`: `CREATE INDEX "account_userId_idx" ON neon_auth.account USING btree ("userId")`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.invitation`

**Kind / use case:** table. Provider-managed organization invitation lifecycle.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `organizationId` | `uuid` | no | `-` | `- / -` |
| `email` | `text` | no | `-` | `- / -` |
| `role` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `expiresAt` | `timestamp with time zone` | no | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `inviterId` | `uuid` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `invitation_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `invitation_email_not_null` / `n` | `NOT NULL email` | deferrable=False, initially deferred=False, validated=True |
| `invitation_expiresAt_not_null` / `n` | `NOT NULL "expiresAt"` | deferrable=False, initially deferred=False, validated=True |
| `invitation_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `invitation_inviterId_fkey` / `f` | `FOREIGN KEY ("inviterId") REFERENCES neon_auth."user"(id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `invitation_inviterId_not_null` / `n` | `NOT NULL "inviterId"` | deferrable=False, initially deferred=False, validated=True |
| `invitation_organizationId_fkey` / `f` | `FOREIGN KEY ("organizationId") REFERENCES neon_auth.organization(id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `invitation_organizationId_not_null` / `n` | `NOT NULL "organizationId"` | deferrable=False, initially deferred=False, validated=True |
| `invitation_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `invitation_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `invitation_email_idx`: `CREATE INDEX invitation_email_idx ON neon_auth.invitation USING btree (email)`; valid=True, ready=True.
- `invitation_organizationId_idx`: `CREATE INDEX "invitation_organizationId_idx" ON neon_auth.invitation USING btree ("organizationId")`; valid=True, ready=True.
- `invitation_pkey`: `CREATE UNIQUE INDEX invitation_pkey ON neon_auth.invitation USING btree (id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.jwks`

**Kind / use case:** table. Provider signing-key metadata; key values not inspected.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `publicKey` | `text` | no | `-` | `- / -` |
| `privateKey` | `text` | no | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `-` | `- / -` |
| `expiresAt` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `jwks_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `jwks_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `jwks_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `jwks_privateKey_not_null` / `n` | `NOT NULL "privateKey"` | deferrable=False, initially deferred=False, validated=True |
| `jwks_publicKey_not_null` / `n` | `NOT NULL "publicKey"` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `jwks_pkey`: `CREATE UNIQUE INDEX jwks_pkey ON neon_auth.jwks USING btree (id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.member`

**Kind / use case:** table. Provider-managed user-to-organization membership.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `organizationId` | `uuid` | no | `-` | `- / -` |
| `userId` | `uuid` | no | `-` | `- / -` |
| `role` | `text` | no | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `member_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `member_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `member_organizationId_fkey` / `f` | `FOREIGN KEY ("organizationId") REFERENCES neon_auth.organization(id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `member_organizationId_not_null` / `n` | `NOT NULL "organizationId"` | deferrable=False, initially deferred=False, validated=True |
| `member_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `member_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |
| `member_userId_fkey` / `f` | `FOREIGN KEY ("userId") REFERENCES neon_auth."user"(id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `member_userId_not_null` / `n` | `NOT NULL "userId"` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `member_organizationId_idx`: `CREATE INDEX "member_organizationId_idx" ON neon_auth.member USING btree ("organizationId")`; valid=True, ready=True.
- `member_pkey`: `CREATE UNIQUE INDEX member_pkey ON neon_auth.member USING btree (id)`; valid=True, ready=True.
- `member_userId_idx`: `CREATE INDEX "member_userId_idx" ON neon_auth.member USING btree ("userId")`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.organization`

**Kind / use case:** table. Provider-managed organization identity.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `slug` | `text` | no | `-` | `- / -` |
| `logo` | `text` | yes | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `-` | `- / -` |
| `metadata` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `organization_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `organization_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `organization_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `organization_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `organization_slug_key` / `u` | `UNIQUE (slug)` | deferrable=False, initially deferred=False, validated=True |
| `organization_slug_not_null` / `n` | `NOT NULL slug` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `neon_auth.invitation` / `invitation_organizationId_fkey`: `FOREIGN KEY ("organizationId") REFERENCES neon_auth.organization(id) ON DELETE CASCADE`.
- `neon_auth.member` / `member_organizationId_fkey`: `FOREIGN KEY ("organizationId") REFERENCES neon_auth.organization(id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `organization_pkey`: `CREATE UNIQUE INDEX organization_pkey ON neon_auth.organization USING btree (id)`; valid=True, ready=True.
- `organization_slug_key`: `CREATE UNIQUE INDEX organization_slug_key ON neon_auth.organization USING btree (slug)`; valid=True, ready=True.
- `organization_slug_uidx`: `CREATE UNIQUE INDEX organization_slug_uidx ON neon_auth.organization USING btree (slug)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.project_config`

**Kind / use case:** table. Provider project authentication configuration; values not inspected.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `endpoint_id` | `text` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `trusted_origins` | `jsonb` | no | `-` | `- / -` |
| `social_providers` | `jsonb` | no | `-` | `- / -` |
| `email_provider` | `jsonb` | yes | `-` | `- / -` |
| `email_and_password` | `jsonb` | yes | `-` | `- / -` |
| `allow_localhost` | `boolean` | no | `-` | `- / -` |
| `plugin_configs` | `jsonb` | yes | `-` | `- / -` |
| `webhook_config` | `jsonb` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `project_config_allow_localhost_not_null` / `n` | `NOT NULL allow_localhost` | deferrable=False, initially deferred=False, validated=True |
| `project_config_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `project_config_endpoint_id_key` / `u` | `UNIQUE (endpoint_id)` | deferrable=False, initially deferred=False, validated=True |
| `project_config_endpoint_id_not_null` / `n` | `NOT NULL endpoint_id` | deferrable=False, initially deferred=False, validated=True |
| `project_config_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `project_config_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `project_config_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `project_config_social_providers_not_null` / `n` | `NOT NULL social_providers` | deferrable=False, initially deferred=False, validated=True |
| `project_config_trusted_origins_not_null` / `n` | `NOT NULL trusted_origins` | deferrable=False, initially deferred=False, validated=True |
| `project_config_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `project_config_endpoint_id_key`: `CREATE UNIQUE INDEX project_config_endpoint_id_key ON neon_auth.project_config USING btree (endpoint_id)`; valid=True, ready=True.
- `project_config_pkey`: `CREATE UNIQUE INDEX project_config_pkey ON neon_auth.project_config USING btree (id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.session`

**Kind / use case:** table. Provider-managed authenticated session metadata.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `expiresAt` | `timestamp with time zone` | no | `-` | `- / -` |
| `token` | `text` | no | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `updatedAt` | `timestamp with time zone` | no | `-` | `- / -` |
| `ipAddress` | `text` | yes | `-` | `- / -` |
| `userAgent` | `text` | yes | `-` | `- / -` |
| `userId` | `uuid` | no | `-` | `- / -` |
| `impersonatedBy` | `text` | yes | `-` | `- / -` |
| `activeOrganizationId` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `session_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `session_expiresAt_not_null` / `n` | `NOT NULL "expiresAt"` | deferrable=False, initially deferred=False, validated=True |
| `session_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `session_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `session_token_key` / `u` | `UNIQUE (token)` | deferrable=False, initially deferred=False, validated=True |
| `session_token_not_null` / `n` | `NOT NULL token` | deferrable=False, initially deferred=False, validated=True |
| `session_updatedAt_not_null` / `n` | `NOT NULL "updatedAt"` | deferrable=False, initially deferred=False, validated=True |
| `session_userId_fkey` / `f` | `FOREIGN KEY ("userId") REFERENCES neon_auth."user"(id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `session_userId_not_null` / `n` | `NOT NULL "userId"` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `session_pkey`: `CREATE UNIQUE INDEX session_pkey ON neon_auth.session USING btree (id)`; valid=True, ready=True.
- `session_token_key`: `CREATE UNIQUE INDEX session_token_key ON neon_auth.session USING btree (token)`; valid=True, ready=True.
- `session_userId_idx`: `CREATE INDEX "session_userId_idx" ON neon_auth.session USING btree ("userId")`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.user`

**Kind / use case:** table. Provider-managed account identity; private user data not inspected.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `email` | `text` | no | `-` | `- / -` |
| `emailVerified` | `boolean` | no | `-` | `- / -` |
| `image` | `text` | yes | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `updatedAt` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `role` | `text` | yes | `-` | `- / -` |
| `banned` | `boolean` | yes | `-` | `- / -` |
| `banReason` | `text` | yes | `-` | `- / -` |
| `banExpires` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `user_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `user_emailVerified_not_null` / `n` | `NOT NULL "emailVerified"` | deferrable=False, initially deferred=False, validated=True |
| `user_email_key` / `u` | `UNIQUE (email)` | deferrable=False, initially deferred=False, validated=True |
| `user_email_not_null` / `n` | `NOT NULL email` | deferrable=False, initially deferred=False, validated=True |
| `user_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `user_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `user_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `user_updatedAt_not_null` / `n` | `NOT NULL "updatedAt"` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `user_email_key`: `CREATE UNIQUE INDEX user_email_key ON neon_auth."user" USING btree (email)`; valid=True, ready=True.
- `user_pkey`: `CREATE UNIQUE INDEX user_pkey ON neon_auth."user" USING btree (id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `neon_auth.verification`

**Kind / use case:** table. Provider-managed verification challenges; values not inspected.

**Owner:** provider-managed observed metadata; no checked-in project migration or MathBank consumer found. Do not edit using corpus migration tooling.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `identifier` | `text` | no | `-` | `- / -` |
| `value` | `text` | no | `-` | `- / -` |
| `expiresAt` | `timestamp with time zone` | no | `-` | `- / -` |
| `createdAt` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |
| `updatedAt` | `timestamp with time zone` | no | `CURRENT_TIMESTAMP` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `verification_createdAt_not_null` / `n` | `NOT NULL "createdAt"` | deferrable=False, initially deferred=False, validated=True |
| `verification_expiresAt_not_null` / `n` | `NOT NULL "expiresAt"` | deferrable=False, initially deferred=False, validated=True |
| `verification_id_not_null` / `n` | `NOT NULL id` | deferrable=False, initially deferred=False, validated=True |
| `verification_identifier_not_null` / `n` | `NOT NULL identifier` | deferrable=False, initially deferred=False, validated=True |
| `verification_pkey` / `p` | `PRIMARY KEY (id)` | deferrable=False, initially deferred=False, validated=True |
| `verification_updatedAt_not_null` / `n` | `NOT NULL "updatedAt"` | deferrable=False, initially deferred=False, validated=True |
| `verification_value_not_null` / `n` | `NOT NULL value` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `verification_identifier_idx`: `CREATE INDEX verification_identifier_idx ON neon_auth.verification USING btree (identifier)`; valid=True, ready=True.
- `verification_pkey`: `CREATE UNIQUE INDEX verification_pkey ON neon_auth.verification USING btree (id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** other role: DELETE (grantable=YES); other role: INSERT (grantable=YES); other role: REFERENCES (grantable=YES); other role: SELECT (grantable=YES); other role: TRIGGER (grantable=YES); other role: TRUNCATE (grantable=YES); other role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

