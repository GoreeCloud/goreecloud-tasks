# Calendar Busy-Time Planning Boundary

GoreeCloud Tasks consumes only the privacy-minimized `goreecloud.calendar.busy.v1` projection when Calendar context is used for planning.

## Accepted data

The Tasks consumer accepts only:

- contract schema and version;
- requested range start and end;
- returned interval count; and
- ordered, non-overlapping busy interval start/end timestamps.

The consumer rejects event titles, descriptions, locations, attendees, calendar names, or other unreviewed Calendar content. Intervals must remain inside the declared requested window and include timezone information.

## Current implementation

`api/calendar_busy.py` now validates and normalizes the Calendar busy-time payload into a `PlanningAvailability` value and computes aggregate busy/free duration without requiring event content.

This increment intentionally does **not** introduce a network transport or static service credential. A live Tasks→Calendar request must be backed by an approved per-user/delegated GoreeCloud Identity authorization path. Until that exists and is validated, Tasks must not work around the gap with a shared cross-user token or direct Calendar/Radicale database access.

## Failure isolation

Calendar remains a peer dependency, not a prerequisite for Tasks. Future integration must treat unavailable or invalid Calendar context as optional planning context and keep normal Tasks capture, editing, search, collaboration, and completion flows operational.

## Acceptance boundary

This is source-level consumer-contract work only. It does not claim live Calendar connectivity, production authorization, user-facing scheduling suggestions, Glaze UI 2.1 conformance, or production acceptance.
