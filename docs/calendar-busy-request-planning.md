# Calendar busy-time request planning boundary

Status: Development

GoreeCloud Tasks now has a transport-neutral request-planning boundary for the future authorized Tasks→Calendar busy-time integration.

After the existing delegated Identity authorization gate succeeds, `api/calendar_request.py` validates the selected Calendar reference plus a positive timezone-aware planning window and produces the exact `GET /api/v1/busy-time` method/path/query shape consumed by GoreeCloud Calendar.

The request plan contains only the selected Calendar reference and requested start/end timestamps. It deliberately contains no Tasks owner identity, delegated authorization object, bearer token, cookie, static service credential, Radicale credential, session identifier, or event content.

## Failure isolation

Missing or invalid delegated authorization fails before a request plan is produced. Missing Calendar reference, naive timestamps, and non-positive windows fail locally. Calendar remains optional planning context; these failures must not affect ordinary Tasks capture, editing, search, collaboration, or completion.

## Transport and authority boundary

This module performs no network I/O. Producing a request plan does not establish connectivity, authenticate to Calendar, mint or transmit credentials, or mean Calendar accepted the request. A future live transport must independently establish the approved delegated GoreeCloud Identity context and pass Privacy Shield/Wardveil review before using the plan.

The response boundary remains `goreecloud.calendar.busy.v1` and continues to reject event titles, descriptions, locations, attendees, calendar names, and other unreviewed Calendar content.

Deployment, user-facing planning composition, production authorization, and Stable qualification remain separate gates.
