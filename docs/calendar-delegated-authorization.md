# Calendar delegated authorization boundary

Status: Development

GoreeCloud Tasks now has a fail-closed authorization gate for the future Calendar busy-time transport.

The gate consumes already-validated GoreeCloud Identity claims only. It requires the same Tasks owner, the dedicated `goreecloud-calendar-busy` audience, the narrow `calendar.busy.read` scope, and an unexpired timezone-aware authorization context before a future transport may even attempt the reviewed busy-time request.

The module does not mint, store, log, or define bearer tokens, cookies, static service credentials, Radicale credentials, or cross-user secrets. It also performs no network I/O. Missing, cross-owner, wrong-audience, missing-scope, and expired authorization all fail through one unavailable boundary.

## Failure and authority boundary

Passing this gate does not mean Calendar accepted a request and does not make Calendar required for normal Tasks behavior. Calendar context remains optional planning input; ordinary task capture, editing, search, collaboration, and completion must remain available when Calendar authorization or transport is unavailable.

Live delegated GoreeCloud Identity transport, Privacy Shield/Wardveil acceptance, user-facing planning composition, deployment, and Stable qualification remain separate gates.
