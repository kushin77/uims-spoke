# Firestore Schema (UIMS spoke)

Collections and document shapes used by UIMS services.

## `issue_state` collection
Document id: `<issue_id>`
Fields:
- `issue_id` (string): issue identifier (matches GitHub issue number or canonical id)
- `current_status` (string): e.g., `open`, `closed`, `stale`
- `score` (float): ranking score from Smart Selector
- `version` (int): optimistic version counter for updates
- `assignee` (string|null): current assignee (username or service account)
- `updated_at` (int): epoch seconds of last update (recommended)

Indexes:
- composite index on `(assignee, score)` for unassigned/high-score queries (optional)

Retention and TTL:
- Ephemeral assignment state can be governed via `assignee` TTL logic implemented by the services.

## `locks` collection
Document id: `<resource_id>` (e.g., issue id)
Fields:
- `owner` (string): the owner who currently holds the lock
- `expiry` (int): epoch seconds when the lock expires (TTL-based)

Notes:
- Locks are short lived (30-120s); services SHOULD attempt retries with backoff.
- Lock operations prefer transactional semantics when available; otherwise, create-if-not-exists and overwrite-if-expired patterns are used.

