# Phase 6B.4 Encryption and Corporate Retention Implementation Plan

Prepared: 2026-11-15

Status: planning only. No application code, database schema, migration, or stored
document was modified while producing this document.

## 1. Purpose and Scope

Phase 6B.4 closes the two remaining Milestone 3 findings:

- **SEC-07**: document files and extracted document text are stored in plaintext.
- **SEC-08**: deleting an employee account can cascade-delete documents owned by
  the company.

The implementation must:

1. Encrypt original uploaded files at rest with AES-256-GCM envelope encryption.
2. Encrypt extracted document text and clause text at rest using the same
   per-document data-encryption key (DEK).
3. Preserve existing authorization boundaries: personal documents, company
   documents, case-shared documents, audit reports, and admin/manager actions
   must not gain or lose access except where explicitly described.
4. Retain company-owned documents when an employee is removed from a company or
   the uploader account is deleted.
5. Fail closed on missing keys, wrong keys, tampered ciphertext, or unsupported
   encryption versions. There must be no silent plaintext fallback.
6. Keep the existing report generation, duplicate detection, OCR, retry, and
   deletion workflows working.

Out of scope for this phase:

- Client-side encryption.
- Full-text search over encrypted text.
- A production KMS integration. The design leaves a provider seam for one.
- New retention-policy UI. Backend policy and storage fields are included.
- Automatic company deletion.

## 2. Current-State Audit Findings

### 2.1 Storage and encryption findings

| ID | Finding | Evidence | Impact |
|---|---|---|---|
| F-01 | Original uploads are written as plaintext bytes. | `backend/app/services/storage.py:58-68` uses `destination.write_bytes(data)`. | A filesystem snapshot or upload-volume leak exposes full contracts. |
| F-02 | Extracted text and clause text are plaintext database columns. | `backend/app/models/document.py:40` (`text_content`), `backend/app/models/clause.py:30-31` (`text`, `normalized_text`). | A database or backup leak exposes contract content even if files are encrypted. |
| F-03 | There is no encryption dependency or key configuration. | `backend/requirements.txt` has no `cryptography`; `.env.example` has no document-encryption key. | No mechanism currently exists to encrypt or rotate document data. |
| F-04 | The raw upload is retained only after successful processing. | `backend/app/services/processing.py:490-502` saves the file after extraction; failure paths call `delete_upload` and set `storage_path = None` (`processing.py:576-588`, `283-291`). | Encryption must cover successful documents; failed/retried documents must not leave plaintext files behind. |
| F-05 | The original file is not served by an API; reports are generated from persisted analysis data. | `backend/app/api/documents.py:532-563`, `backend/app/api/audit_reports.py:236-266`, `backend/app/services/report.py:374-377`. | Decryption is needed for processing, migration, and report rendering, not for a current raw-file download endpoint. |
| F-06 | `DocumentRead` still declares `storage_path`, although current manual payloads omit it. | `backend/app/schemas/documents.py:16-24`; tests assert the field is absent from API responses. | A future schema/serialization change could accidentally expose the private path. Remove it from the read schema. |
| F-07 | Stored filenames include the sanitized original filename. | `backend/app/services/storage.py:34-43`, `58-63`. | A storage-layer leak reveals document names even if content is encrypted. This is residual metadata risk; new files should use opaque names. |

### 2.2 Ownership and retention findings

| ID | Finding | Evidence | Impact |
|---|---|---|---|
| F-08 | `documents.user_id` uses `ON DELETE CASCADE`, and `User.documents` uses `delete-orphan`. | `backend/app/models/document.py:16-18`; `backend/app/models/user.py:52-54`. | Deleting an employee user row deletes all company documents uploaded by that employee, including analyses and clauses. This is SEC-08. |
| F-09 | Company ownership is `company_id`, but the uploader FK is still the cascade owner. | `backend/app/models/document.py:19-25`; authorization in `backend/app/api/documents.py:302-339`. | Corporate documents are not truly independent of the uploader account. |
| F-10 | Removing a team member already preserves documents. | `backend/app/api/company.py:242-271` sets `company_id = NULL` and `company_role = NULL` on the user only. | The membership-removal path is correct, but account deletion still bypasses it. Add regression coverage for both paths. |
| F-11 | `documents.company_id` uses `ON DELETE SET NULL`. | `backend/app/models/document.py:21-25`. | If a company row is ever deleted, company documents become personal/orphaned instead of being retained or explicitly purged. |
| F-12 | There is no account-deletion endpoint. | `backend/app/api/auth.py` exposes register, login, logout, change-password, and me only. | SEC-08 currently manifests through direct database/admin deletion; any future account deletion must be designed as a controlled service, not a raw `db.delete(user)`. |
| F-13 | There is no retention policy, legal-hold flag, or purge job. | `docs/LAUNCH_CHECKLIST.md:96` still says `[retention period to be confirmed]`. | Corporate retention cannot be audited or automated yet. Default behavior must remain "retain indefinitely" until policy is approved. |
| F-14 | Case links are separate from document ownership. | `CaseDocument` links documents to cases; document deletion cascades the link, not the reverse. | Company documents survive employee removal and case closure. Any retention purge must consider active/closed case links. |
| F-15 | Tests do not cover encryption, wrong-key behavior, tampering, or account-deletion retention. | No `test_document_crypto.py`; existing tests assert plaintext file paths and extracted text. | New security tests are required before implementation is accepted. |

### 2.3 Existing lifecycle that must be preserved

- Upload creates a `PROCESSING` row, extracts/segments/analyzes in a worker
  thread, then stores the original and extracted text
  (`backend/app/services/processing.py:594-712`, `440-591`).
- Duplicate detection uses the plaintext SHA-256 `content_hash` scoped by
  company or personal owner (`processing.py:624-701`;
  `backend/app/models/document.py:69-84`). Encryption must not change dedupe
  semantics.
- Failed documents retry in place and delete the previous stored file
  (`processing.py:139-163`).
- Document deletion removes analyses, findings, clauses, the row, and the
  managed file (`processing.py:166-180`). Delete-all is scoped by personal user
  or company (`processing.py:182-214`).
- Reports are generated from persisted analyses/clauses, not from the original
  file (`backend/app/services/report.py:438-443`).
- The frontend does not see storage paths and does not need changes if the API
  continues to return decrypted text.

### 2.4 Complete Codebase Inventory of Document Operations

An exhaustive audit of every location where documents are uploaded, stored, read, downloaded, processed, encrypted, or deleted in the codebase reveals the following operation mapping:

| Stage / Operation | File and Lines | Functions / Handlers | Description and Security Characteristics |
|---|---|---|---|
| **1. Upload Ingestion** | `backend/app/api/documents.py:406-448` | `upload_document` | Receives multipart upload, enforces upload size limits (`max_upload_size_mb`), resolves company role/ownership, reads upload bytes into memory, and delegates to async worker. |
| **2. Async Offload** | `backend/app/services/processing.py:750-770` | `process_upload_async`, `_process_upload_worker` | Offloads processing to `ThreadPoolExecutor` using in-memory byte buffer; no intermediate disk files created. |
| **3. Processing Entry & Deduplication** | `backend/app/services/processing.py:594-712` | `process_upload` | Computes SHA-256 `content_hash` on plaintext bytes; performs tenant-scoped duplicate detection (`(company_id, hash)` or `(user_id, hash)`); creates `PROCESSING` record. |
| **4. Format Parsing & Validation** | `backend/app/services/extraction.py:546-630` | `validate_and_extract` | Inspects magic bytes, validates MIME types, protects against zip-bombs (`_assert_magic`), and dispatches to format-specific extractors (`_extract_pdf`, `_extract_docx`, `_extract_txt`). |
| **5. OCR Pipeline** | `backend/app/services/extraction.py:270-350`, `backend/app/services/ocr.py:270-320` | `_apply_ocr`, `ocr_page`, `ocr_layout.py`, `ocr_merge.py` | Extracts scanned PDF pages in memory via PyMuPDF/RapidOCR without writing intermediate images or plaintext files to disk. |
| **6. Segmentation & AI Analysis** | `backend/app/services/segmentation.py:110-180`, `backend/app/services/analysis.py:440-520` | `segment_clauses`, `analyze_segments` | Parses contract clauses and evaluates legal risk findings against rule engine entirely within memory buffers. |
| **7. Clause Persistence** | `backend/app/services/processing.py:296-410` | `persist_clauses` | Persists `Clause` records into database. Currently writes plaintext `text` and `normalized_text`; must encrypt with document DEK before DB insert. |
| **8. File Storage at Rest** | `backend/app/services/storage.py:58-68` | `save_upload`, `upload_dir`, `is_managed_path` | Currently writes raw unencrypted bytes to disk via `destination.write_bytes(data)`. Must be replaced with atomic encrypted writes (`JSC1` envelope with document DEK). |
| **9. Document Detail Read** | `backend/app/api/documents.py:496-499`, `241-255` | `get_document`, `_detail_payload`, `_page_payloads` | Enforces ownership and case/company sharing via `_readable_document_conditions`; returns document text and clauses. Must unwrap DEK and decrypt fields for authorized caller. |
| **10. Document List Read** | `backend/app/api/documents.py:461-494`, `87-123` | `list_documents`, `_summary_payload` | Returns document metadata and analysis summaries; does not return full text, avoiding unnecessary decryption overhead. |
| **11. Analysis Detail Read** | `backend/app/api/documents.py:567-590`, `149-167` | `get_analysis`, `_analysis_payload` | Returns analysis metadata and clause findings. Must decrypt clause text if presented in analysis payload. |
| **12. Company Audit Reports Read** | `backend/app/api/audit_reports.py:87-156`, `158-226`, `228-234` | `list_audit_reports`, `audit_overview`, `get_audit_report` | Queries documents scoped to `company_id`. Operates on aggregated analysis metadata. |
| **13. Case Sharing** | `backend/app/api/cases.py:910-940`, `backend/app/api/documents.py:257-273` | `attach_case_document`, `_shared_document_ids` | Associates document with case via `CaseDocument`; authorizes assigned lawyer and case owner to decrypt and view document. |
| **14. PDF Report Generation & Download** | `backend/app/api/documents.py:533-564`, `backend/app/api/audit_reports.py:237-268`, `backend/app/services/report.py:438-665` | `get_analysis_report`, `download_audit_report`, `build_report_pdf` | Generates on-the-fly PDF reports from in-memory decrypted clauses using PyMuPDF; streams PDF to client without writing temporary report files to disk. |
| **15. Raw File Downloads** | N/A | None | **None exists in API by design.** The application never serves raw uploaded binaries, preventing direct link exfiltration. |
| **16. Single Document Deletion** | `backend/app/api/documents.py:518-530`, `backend/app/services/processing.py:166-180` | `delete_document`, `_ensure_can_delete` | Validates deletion permissions, removes database rows (findings, analyses, clauses, document), and deletes encrypted file from disk via `delete_upload`. |
| **17. Bulk Deletion** | `backend/app/api/documents.py:502-515`, `backend/app/services/processing.py:182-218` | `delete_all_documents` | Scoped by tenant (`company_id` or `user_id` where `company_id IS NULL`); deletes all matching rows and cleans up encrypted disk files. |
| **18. Retry & Failure Cleanup** | `backend/app/services/processing.py:139-163`, `285-294` | `_prepare_retry`, `_finalize_failed` | Removes old file upload (`delete_upload`), clears old analysis/findings, resets status to `PROCESSING`, and clears `storage_path`. |
| **19. Stale Processing Sweep** | `backend/app/services/processing.py:86-116`, `backend/main.py:33-40` | `recover_stale_documents`, `_stale_recovery_loop` | Background sweep transitions stuck `PROCESSING` documents to `FAILED` so they can be retried cleanly. |

## 3. Security Invariants

The implementation must satisfy all of the following:

1. A successfully processed document has no plaintext bytes in
   `<data_dir>/uploads`.
2. `documents.text_content`, `clauses.text`, and `clauses.normalized_text` do
   not contain plaintext contract text in the database.
3. Authorized API responses and generated reports still return the correct
   plaintext.
4. Unauthorized users still receive `404` for documents they cannot read; no
   new existence leak is introduced.
5. A ciphertext that is modified, truncated, or moved to another document/field
   is rejected; the application never returns partial plaintext.
6. A missing, unknown, or invalid key is a hard failure. There is no fallback to
   plaintext and no fallback to a default key.
7. A company document remains owned by the company and readable by authorized
   company members after the uploader leaves the company or the uploader account
   is deleted.
8. A legal hold blocks deletion. Retention expiry never deletes a document that
   is on hold or linked to a case that still requires retention.
9. Keys never appear in logs, API responses, database rows in plaintext, test
   fixtures committed to the repository, or source control.
10. Existing Phase 6B.1-6B.3 controls remain intact: tenant-scoped dedupe,
    verified-lawyer case access, rate limiting, token versioning, and
    server-side session revocation.

## 4. Recommended Architecture

### 4.1 Key hierarchy

Use a two-level envelope:

```text
Key-encryption key (KEK), versioned, from secret configuration
        |
        |  AES-256-GCM wrap
        v
Per-document data-encryption key (DEK), 32 random bytes
        |
        |  AES-256-GCM encrypt
        +--> original file bytes
        +--> documents.text_content
        +--> each clauses.text
        +--> each clauses.normalized_text
```

Properties:

- Each document gets a unique DEK. Compromise of one DEK does not decrypt other
  documents.
- The DEK is stored wrapped by the active KEK on the `documents` row. The
  database never stores an unwrapped DEK.
- The KEK is not stored in the database. Losing it without a backup makes
  encrypted documents unrecoverable, so key backup is an operational control.
- KEK rotation only re-wraps DEKs. Files and text fields do not need to be
  re-encrypted.
- DEK compromise requires re-encrypting that document's file and text fields
  with a new DEK.

Recommended configuration:

```dotenv
DOCUMENT_ENCRYPTION_ACTIVE_KEY_ID=v1
DOCUMENT_ENCRYPTION_KEYS={"v1":"<base64-encoded-32-byte-key>"}
```

Implementation details:

- Add `cryptography` to `backend/requirements.txt` and use
  `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.
- Parse and validate the key ring at startup:
  - active key id must exist;
  - every value must decode to exactly 32 bytes;
  - unknown/duplicate key ids are rejected;
  - production and staging fail startup if the configuration is absent or
    invalid;
  - test configuration is explicit in `backend/tests/conftest.py`.
- Do not derive the document key from `SECRET_KEY`. They have different
  rotation and exposure lifecycles.
- Keep the key ring in memory only. Never log key material or wrapped/unwrapped
  key material.
- Future KMS integration can replace the environment key ring behind a
  `KeyProvider` interface without changing the envelope format.

### 4.2 Envelope formats

Use explicit versioned formats so old data remains readable during migration.

**File envelope**

```text
magic "JSC1" | version 1 | nonce (12 bytes) | AES-256-GCM ciphertext + tag
```

The DEK used for the file is the document DEK. The file header does not need the
KEK id because the document row stores `encryption_key_id`. The file is written
atomically: write a temporary file in the managed upload directory, flush/fsync,
then `os.replace` to the final path.

Store new encrypted uploads under opaque names such as `<uuid>.jse`; do not
embed the original filename in the path. The original filename remains in
`documents.filename` for display.

**Database text envelope**

```text
"JSE1" | version 1 | nonce (12 bytes) | AES-256-GCM ciphertext + tag
```

Store the envelope as a base64 text value in the existing `Text` columns. The
document row provides the DEK. `encryption_version = 1` indicates that text
columns are encrypted; `encryption_version = 0` is reserved for explicitly
legacy plaintext rows during migration.

**Wrapped DEK envelope**

Store on `documents`:

- `encryption_version` smallint, not null, default `0`.
- `encryption_key_id` varchar(32), nullable.
- `dek_wrapped` text, nullable: base64 of `nonce | wrapped-DEK ciphertext+tag`.

The wrapped DEK AEAD associated data must bind:

```text
"juriscan:dek:v1:" + document_id + ":" + encryption_key_id
```

The file AEAD associated data must bind:

```text
"juriscan:file:v1:" + document_id + ":" + content_hash
```

The text AEAD associated data must bind:

```text
"juriscan:text:v1:" + document_id + ":" + field_name
```

For clause fields, `field_name` includes the stable clause number, for example
`clause:3:text` and `clause:3:normalized_text`. This prevents ciphertext from
being swapped between documents or between fields without detection.

The KEK id is intentionally not part of the text AAD. It is bound only to the
wrapped DEK, so a KEK rotation can re-wrap the DEK and update
`encryption_key_id` without re-encrypting file or text ciphertext. Including the
rotating KEK id in text AAD would make re-wrap-only rotation undecryptable.

Nonces must be randomly generated per encryption operation and never reused
with the same DEK. AES-GCM's 96-bit random nonce is appropriate at this data
volume; record a rotation/backfill path if a document is ever re-encrypted many
times.

### 4.3 Database fields to encrypt

Encrypt:

- `documents.text_content`
- `clauses.text`
- `clauses.normalized_text`

Do not encrypt:

- `documents.title`, `filename`, `file_type`, `mime_type`, `status`,
  `content_hash`, page/word counts, language, timestamps.
- `clauses.heading`, numbering, offsets, page numbers, labels, risk levels,
  OCR quality metadata.
- `analyses.risk_score`, status, model name, timestamps.
- `risk_findings` rule/title/severity/citation/recommendation fields. These are
  static rule descriptions in the current engine, not quoted contract text.
  `RiskFinding.description` must be re-audited if rule text later starts
  quoting clause content.

Rationale: list/search/reporting code depends on unencrypted metadata, and the
current rules do not copy contract text into finding fields. The full contract
text is the high-risk payload.

### 4.4 Application data flow

**New upload**

1. `process_upload` computes the plaintext content hash and scopes duplicate
   detection exactly as today.
2. For a new document, generate a DEK and wrap it with the active KEK before
   committing the `PROCESSING` row.
3. `run_processing` extracts and analyzes plaintext in memory as today.
4. Before `save_upload`, encrypt the original bytes with the document DEK.
5. Encrypt `text_content` and every clause text/normalized text before assigning
   them to ORM fields.
6. Commit the row, clauses, and analysis in the existing transaction.
7. On failure, delete any encrypted file and clear text exactly as today.

**Read/detail**

- `_detail_payload` loads the document DEK once, decrypts `text_content`, and
  decrypts each clause before building the response.
- Page spans and metadata are unchanged.
- A decryption failure raises a controlled `DocumentEncryptionError`; it does
  not return partial text and does not fall back to storing/reading plaintext.

**Report**

- Decrypt clauses before `build_report_pdf`.
- Reports remain generated from persisted analysis data; no original-file
  download is introduced.
- The same protection applies to the company audit-report PDF endpoint in
  `backend/app/api/audit_reports.py`.

**Delete/retry**

- Retry deletes the old encrypted file and resets metadata; it must also decide
  whether to reuse or replace the DEK. Recommended: generate a new DEK on retry
  and re-wrap it, so a failed partial file cannot be confused with a new run.
- Delete removes the encrypted file after the DB commit, as today.
- Delete-all collects encrypted paths before deleting rows, then removes files.

**Legacy read path**

During migration only, code may read `encryption_version = 0` rows as plaintext.
This is an explicit marker, not a fallback. Once all documents are migrated and
verified, remove the legacy read branch in a later release and make
`encryption_version = 1` the enforced state.

## 5. Corporate Ownership and Retention Design

### 5.1 Ownership semantics

Recommended minimal, compatible change set:

1. Make `documents.user_id` nullable with `ON DELETE SET NULL`.
2. Remove `delete-orphan` from `User.documents`; use a passive relationship so a
   user deletion does not cascade documents.
3. Keep `user_id` as the uploader pointer. For personal documents it is also the
   owner. For company documents the company is the owner; `user_id` is audit
   metadata.
4. Change `documents.company_id` to `ON DELETE RESTRICT`. Do not allow a company
   deletion to silently turn corporate documents into personal data.
5. Do not add a raw `DELETE /auth/account` implementation that calls
   `db.delete(user)` directly. Any account-deletion endpoint must use a service
   that handles personal data, company retention, last-admin rules, and legal
   hold.

Authorization impact:

- Company documents are still read through `Document.company_id == user.company_id`
  (`backend/app/api/documents.py:323-339`), so all current company members keep
  access even if the uploader is deleted.
- Personal documents remain visible through `Document.user_id == user.id` and
  `company_id IS NULL`.
- Single-document deletion for a company manager still works through
  `_ensure_can_delete`; a regular member's uploader-based delete path must be
  reviewed after `user_id` becomes nullable. Recommended rule: a member may
  delete a company document they uploaded while they are still a member; a
  manager/admin may delete any company document.
- No API response should expose `user_id` after the ownership semantics change.
  Remove `user_id` from read schemas if it is not required.

### 5.2 Account deletion service (future endpoint, required semantics)

When an account-deletion endpoint is added:

- Require re-authentication and explicit confirmation.
- Revoke all sessions by incrementing `token_version` and deleting/expiring
  sessions.
- If the user is the last active `COMPANY_ADMIN`, block deletion until another
  admin is appointed.
- For personal documents (`company_id IS NULL`):
  - Delete the row, clauses, analyses, findings, and encrypted file after
    retention/legal-hold checks.
  - If a document is attached to an active case, block deletion or require a
    separate case-retention decision; do not silently destroy case evidence.
- For company documents (`company_id IS NOT NULL`):
  - Retain the row, clauses, analyses, findings, and encrypted file.
  - Set `user_id = NULL` so the uploader FK no longer cascades.
  - Preserve the uploader identity in an audit-safe snapshot or audit event if
    required by corporate policy. Do not rely on the deleted user row for audit.
- Anonymize or delete remaining personal account data; do not leave credentials
  or active tokens.

The Phase 6B.4 schema and tests should prove the retention guarantee. The
account-deletion UI/endpoint can be a follow-up, but the data model must already
be safe against direct user deletion.

### 5.3 Company membership removal

Current behavior is correct and should remain:

- `remove_team_member` clears only the user's `company_id` and `company_role`.
- Company documents keep `company_id` and remain in the company workspace.
- The removed user loses company-scope access because `_company_scope_id`
  returns `None`.
- The removed user's personal documents are unaffected.

Add regression tests that combine membership removal with company-document
listing, audit reports, and account deletion.

### 5.4 Retention policy and legal hold

Add:

- `companies.retention_days` integer nullable. `NULL` means use the system
  default; `0` means indefinite retention.
- `documents.retention_until` timestamptz nullable.
- `documents.legal_hold` boolean not null default `false`.
- A `DOCUMENT_RETENTION_DAYS` setting with default `0` (no automatic deletion)
  until the business/legal retention period is confirmed.

Rules:

1. Explicit user/company-admin deletion remains immediate unless
   `legal_hold = true`; a held document returns `409 legal_hold_active`.
2. Automatic purge only deletes documents whose `retention_until` has passed,
   `legal_hold` is false, and which are not linked to a case requiring
   retention. Default behavior is no automatic purge.
3. Company documents are retained when an employee leaves or the uploader
   account is deleted.
4. Company deletion is restricted by the FK and is not exposed as an API. A
   future company-deletion workflow must explicitly decide transfer vs purge
   and must respect legal hold.
5. Retention actions produce an audit record (structured log minimum; a
   retention-event table is recommended) containing document id, company id,
   actor, reason, and timestamp, without document content.
6. The retention period remains an open policy item:
   `docs/LAUNCH_CHECKLIST.md:96` must be completed before automatic purge is
   enabled.

### 5.5 Purge job

If enabled, run a bounded background loop from `backend/main.py` lifespan
alongside the existing stale-document sweep:

- acquire a small batch with row locks (`FOR UPDATE SKIP LOCKED` on PostgreSQL);
- skip legal hold and active case links;
- delete results and encrypted files in the same order as the existing delete
  service;
- log counts and failures;
- make the job idempotent and safe to run in multiple workers;
- keep it disabled by default until retention policy is approved.

## 6. Migration Strategy

Do not create migrations during this audit. The implementation should use two
reviewable migrations plus a data-backfill command.

### 6.1 Migration A: encryption metadata

Add to `documents`:

- `encryption_version` smallint not null default `0`;
- `encryption_key_id` varchar(32) nullable;
- `dek_wrapped` text nullable.

Add indexes only if query plans require them; no plaintext data is moved by the
schema migration. Existing rows remain explicitly legacy (`version = 0`).

### 6.2 Migration B: ownership and retention

- Alter `documents.user_id` to nullable and change the FK from `CASCADE` to
  `SET NULL`.
- Change `documents.company_id` FK from `SET NULL` to `RESTRICT`.
- Add `companies.retention_days`.
- Add `documents.retention_until` and `documents.legal_hold`.
- Update the SQLAlchemy models and relationships in the same change.
- Use `batch_alter_table` for SQLite test compatibility; use inspected
  constraint names on PostgreSQL.
- Update migration tests to assert both upgrade and downgrade behavior.

### 6.3 Data backfill

Create an idempotent command, for example:

```text
python -m app.cli.encrypt_documents --dry-run
python -m app.cli.encrypt_documents --batch-size 25
python -m app.cli.encrypt_documents --verify-only
```

For each `encryption_version = 0` document:

1. Generate a DEK and wrap it with the active KEK.
2. If a managed plaintext file exists:
   - read it and verify its SHA-256 against `content_hash` when present;
   - encrypt to a new opaque path;
   - update `storage_path` and key metadata;
   - commit;
   - only then delete the old plaintext file.
3. Encrypt `text_content` and each clause's `text`/`normalized_text` using the
   document DEK and field-bound AAD.
4. Set `encryption_version = 1` and commit the batch.
5. Verify by decrypting and comparing the plaintext hash/length before
   considering the document migrated.

Operational rules:

- Take and verify a database plus upload-volume backup first.
- Use a maintenance window for the first rollout, or a two-release dual-read
  rollout:
  - Release A: schema + crypto service + explicit legacy read path; writes can
    remain legacy behind a disabled feature flag.
  - Backfill to version 1.
  - Release B: enable encrypted writes; keep legacy reads for remaining rows.
  - Later release: remove legacy reads after all rows are version 1.
- The backfill must be resumable by document id, skip already encrypted rows,
  and support a single-document retry.
- Never delete the only plaintext copy until the encrypted row and file have
  been committed and verified.
- Do not run the backfill inside an Alembic migration that requires the
  application key ring; key handling belongs to the application command.

### 6.4 Key rotation

Add a command:

```text
python -m app.cli.rotate_document_keys --new-key-id v2 --dry-run
python -m app.cli.rotate_document_keys --new-key-id v2
```

It unwraps each DEK with its recorded KEK, wraps it with the new active KEK, and
updates `encryption_key_id`/`dek_wrapped`. Files and text remain unchanged.
Keep the old KEK in the ring until all rows are re-wrapped, then retire it after
a verification pass and backup.

## 7. Implementation Order

### Phase 0: Approval and guardrails

- Approve this plan, the retention period, and the key-management approach.
- Confirm no production implementation starts before the key backup/restore
  procedure exists.
- Add the encryption tests to the acceptance gate.

### Phase 1: Crypto foundation

- Add `cryptography` dependency.
- Add key-ring settings, validation, and tests.
- Add `backend/app/services/document_crypto.py`:
  - key provider interface;
  - KEK wrap/unwrap;
  - AES-GCM file/text envelope helpers;
  - AAD construction;
  - explicit `DocumentEncryptionError`.
- Add `.env.example` entries and a key-generation command. Never add a real key
  to the repository.
- No document writes are encrypted yet; tests use round-trip fixtures.

### Phase 2: Schema and dual-read

- Add encryption columns and update models.
- Implement explicit legacy read support (`version = 0`) and decrypt support for
  version 1.
- Add a disabled write flag. Verify that `alembic check` passes and existing
  tests still pass with legacy rows.

### Phase 3: Encrypted write path

- Generate/attach DEKs during upload.
- Encrypt original files and document/clause text on new writes.
- Adapt detail, report, audit-report, retry, and delete paths.
- Remove `storage_path` and `user_id` from read schemas where no longer needed.
- Add end-to-end tests proving no plaintext reaches disk or the target columns.
- Enable encrypted writes in test and then in the target environment after the
  migration command is ready.

### Phase 4: Backfill and key rotation

- Run a dry run on a database copy.
- Back up and verify the real database and uploads.
- Migrate existing documents in batches.
- Run verification and sample decryption/report generation.
- Run a key-rotation dry run and a full re-wrap.
- Keep legacy reads only as long as required for the remaining version-0 rows.

### Phase 5: Corporate retention

- Make `user_id` nullable and `SET NULL`; remove `delete-orphan`.
- Change `company_id` to `RESTRICT`.
- Add retention/legal-hold fields and update delete paths.
- Implement the account-deletion service semantics and tests.
- Add the optional purge loop, disabled by default.
- Resolve and document the launch retention period before enabling purge.

### Phase 6: Final hardening

- Remove the plaintext fallback once all rows are version 1.
- Run the full backend and frontend suites.
- Update operations docs: backup/restore, key storage, rotation, disaster
  recovery, and incident response for a suspected key compromise.
- Update the security audit status for SEC-07 and SEC-08 only after the tests
  demonstrate both the encryption and retention guarantees.

## 8. Testing Strategy

### 8.1 New crypto unit tests

Create `backend/tests/test_document_crypto.py` covering:

- valid key ring parsing and active-key selection;
- startup rejection of missing, malformed, short, or unknown keys;
- DEK wrap/unwrap round trip;
- file and text round trip;
- unique nonces across repeated encryption;
- tampered ciphertext/tag rejection;
- wrong document id or field name in file/text AAD rejection;
- wrong document id or key id in wrapped-DEK AAD rejection;
- wrong KEK rejection;
- explicit legacy version read;
- no plaintext fallback when a version-1 envelope is invalid;
- key rotation re-wraps without changing file/text ciphertext;
- secrets do not appear in exception messages or logs.

### 8.2 Storage tests

Update `backend/tests/test_documents.py` and add coverage for:

- uploaded file bytes do not contain a known plaintext marker;
- the stored file has a valid `JSC1` header;
- decrypting the stored file returns the original bytes and hash;
- original filename is not embedded in new opaque paths;
- delete removes the encrypted file;
- retry replaces the old encrypted file and does not leave plaintext;
- path traversal and managed-directory checks still apply.

### 8.3 API and report tests

- Upload a TXT/DOCX/PDF with a unique marker; assert the marker is absent from
  the raw `documents.text_content` and `clauses.text` columns.
- Assert `GET /documents/{id}` still returns the marker in `text_content` and
  clauses for the owner.
- Assert the PDF report contains analysis data and clause text.
- Assert company audit-report PDF generation still works.
- Assert unauthorized users still receive 404 and no ciphertext/metadata leak.
- Assert list summaries do not decrypt or expose text.
- Assert `storage_path` is absent from every API response.
- Assert a tampered ciphertext produces a controlled error without partial
  content.

### 8.4 Migration tests

Extend `backend/tests/test_migrations.py`:

- new encryption columns exist with expected nullability/defaults;
- `user_id` is nullable with `SET NULL` semantics;
- `company_id` is `RESTRICT`;
- retention columns exist;
- upgrade/downgrade on SQLite and PostgreSQL;
- `alembic check` remains clean;
- version-0 and version-1 rows co-exist during the transition;
- backfill is idempotent and skips version-1 rows;
- backfill does not delete data when key validation or decryption fails.

### 8.5 Retention tests

Extend `backend/tests/test_document_isolation.py` and
`backend/tests/test_company_team.py`:

- deleting an employee user row leaves company documents, clauses, analyses,
  findings, and encrypted files intact;
- the company can still list/read/report the retained document;
- personal documents follow the explicit account-deletion policy;
- removing a team member revokes access but retains company documents;
- deleting a company is restricted or requires an explicit workflow;
- legal hold blocks single and bulk deletion;
- bulk delete never touches another tenant;
- retention expiry skips legal hold and active case links;
- last-company-admin deletion is blocked.

### 8.6 Regression and operational tests

- Full backend suite: target all existing tests plus new tests, zero failures.
- Frontend unit tests, lint, TypeScript build, and production build: unchanged
  behavior, zero new errors.
- Backup/restore test: restore into a disposable database, decrypt a sample
  document, and generate a report.
- Key-rotation test on a disposable copy.
- Performance check at the 25 MB upload limit: memory headroom and acceptable
  latency.
- Log scan: no key material, no plaintext document markers in application logs.

## 9. Affected Files

### New files

- `backend/app/services/document_crypto.py`: key ring, envelope, AAD, errors.
- `backend/app/cli/encrypt_documents.py`: idempotent backfill/verification.
- `backend/app/cli/rotate_document_keys.py`: DEK re-wrap command.
- `backend/tests/test_document_crypto.py`: crypto unit/security tests.
- Possibly `backend/tests/test_retention.py`: retention and account-deletion
  tests if they do not fit the existing isolation/team files.

### Backend changes

- `backend/requirements.txt`: add `cryptography`.
- `backend/app/config/settings.py`: key ring, active key id, retention settings,
  fail-fast validation.
- `backend/app/models/document.py`: encryption metadata, nullable `user_id`,
  `SET NULL` FK, `RESTRICT` company FK, retention/legal-hold fields.
- `backend/app/models/user.py`: remove document `delete-orphan`; passive
  relationship.
- `backend/app/models/company.py`: `retention_days` and company document
  relationship semantics.
- `backend/app/models/clause.py`: document-key-based text decryption support or
  service integration; no plaintext fallback.
- `backend/app/schemas/documents.py`: remove `storage_path` from read schema;
  remove `user_id` from public read schema; add retention fields only if
  exposed.
- `backend/app/services/storage.py`: encrypted save/read, opaque filenames,
  atomic replacement, hash verification, managed-path delete.
- `backend/app/services/processing.py`: DEK lifecycle, encrypted writes,
  decryption for segmentation/retry, delete/delete-all, failed-run cleanup.
- `backend/app/api/documents.py`: decrypted detail/report responses, retention
  checks, account/company delete rules.
- `backend/app/api/audit_reports.py`: decrypt clauses for audit PDFs.
- `backend/app/services/report.py`: consume decrypted clause text only; no key
  handling.
- `backend/app/api/company.py`: membership removal regression, retention policy
  fields, company-deletion guard.
- `backend/app/api/auth.py`: future account-deletion endpoint/service hook; no
  raw `db.delete(user)` path.
- `backend/main.py`: optional retention purge lifespan loop.
- `backend/app/core/exceptions.py`: controlled encryption/legal-hold errors.
- `backend/tests/conftest.py`: explicit test key configuration.
- `.env.example`: key ring, active key id, retention settings, generation
  instructions.
- `docker-compose.yml`: pass the encryption key configuration into the backend
  from a secret source; do not bake keys into the image.
- `docs/LAUNCH_CHECKLIST.md`: resolve retention period and add key-management,
  backup, and restore checks.
- `docs/DATA_SECURITY_AUTH_AUDIT.md`: mark SEC-07/SEC-08 status only after
  implementation and verification.

### Frontend

No functional frontend change is expected because the API continues to return
decrypted text and reports. Re-run:

- `npm test`
- `npm run lint`
- `npm run build`

If retention metadata or legal-hold controls are exposed later, update the
company document/settings UI at that time.

## 10. Acceptance Criteria

Phase 6B.4 is complete only when all of the following are true:

1. New uploads are encrypted with a unique DEK; no plaintext file or text
   remains in storage/DB for version-1 documents.
2. Existing documents are migrated and verified, with a tested restore path.
3. Wrong keys, tampering, unknown key ids, and unsupported versions fail closed
   without plaintext fallback.
4. Authorized reads and report downloads return correct plaintext; unauthorized
   reads remain hidden.
5. `storage_path` is not present in any API response.
6. A company document survives employee membership removal and uploader account
   deletion, including its file, clauses, analyses, findings, and audit report.
7. Personal-document deletion follows the explicit account-deletion policy and
   respects active cases and legal hold.
8. Company deletion cannot silently convert retained corporate documents to
   personal/orphan records.
9. Key rotation is tested and documented; old/new keys can co-exist during
   rotation.
10. Full backend/frontend test suites, migration checks, backup/restore checks,
    and security tests pass.
11. No key material or plaintext document content appears in logs or source
    control.

## 11. Open Decisions and Risks

1. **Retention period**: `docs/LAUNCH_CHECKLIST.md:96` is unresolved. Default
   to indefinite retention and do not enable automatic purge until approved.
2. **Account deletion policy for personal documents linked to active cases**:
   block deletion, transfer to the case, or retain under a case-specific policy.
   Do not decide this silently in code.
3. **Uploader audit identity after user deletion**: `user_id = NULL` improves
   retention but loses the uploader link. Add an immutable audit event or
   uploader snapshot if corporate policy requires "who uploaded this".
4. **KMS vs environment key ring**: the design supports an environment key ring
   now and a KMS provider later. Production key custody, backup, and dual-control
   procedures must be agreed before go-live.
5. **Company deletion**: not implemented. The `RESTRICT` FK prevents accidental
   data conversion; a future workflow must decide transfer vs purge.
6. **Title/filename metadata**: remains plaintext for search and display. If
   document names are themselves privileged, plan a later encrypted-name or
   blind-index design.
7. **Rollout model**: a maintenance window is simplest for the local database;
   a two-release dual-read rollout is safer for a live service. Choose before
   the first schema deployment.
8. **Legal hold UI**: the backend flag and deletion guard should be implemented;
   an admin UI can follow if the product needs it in this phase.

## 12. Recommended First Step

After approval of this plan, implement the crypto foundation only:

1. Add the `cryptography` dependency and key-ring configuration validation.
2. Create `backend/app/services/document_crypto.py` with AES-256-GCM
   wrap/unwrap, file/text envelopes, AAD, and explicit failure behavior.
3. Add `backend/tests/test_document_crypto.py` and the test configuration key.
4. Do not change document storage or create migrations until the primitive
   round-trip, tamper, wrong-key, and rotation tests pass.

This isolates the highest-risk cryptographic code from the schema and lifecycle
changes, and gives Phase 6B.4 a verifiable foundation before any stored document
is touched.
