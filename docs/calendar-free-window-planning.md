# Calendar free-window planning

Status: Development source only.

This tranche builds on the validated GoreeCloud Calendar busy-context consumer by adding a pure advisory planner. It computes qualifying free windows as the complement of the already validated Calendar-authoritative busy intervals inside the requested planning range.

## Input boundary

The planner accepts `CalendarBusyContext`, whose peer-client contract contains only:

- generated timestamp;
- requested range; and
- merged busy interval start/end timestamps.

The Calendar consumer continues to reject event titles, descriptions, locations, UIDs, attendees, Calendar subjects, collection identifiers, and unsupported metadata before context becomes trusted Tasks input.

The planner defensively rechecks temporal ordering/range rules so manually constructed invalid context cannot be turned into trustworthy-looking suggestions.

## Planning behavior

`derive_free_windows(...)`:

- returns earliest qualifying complement intervals in deterministic order;
- requires a minimum free-window duration between 5 minutes and 24 hours;
- returns at most 32 windows and defaults to 8;
- accepts only timezone-aware positive planning ranges;
- rejects overlapping, touching, out-of-range, naive, or otherwise noncanonical busy intervals; and
- creates no database record or external side effect.

## Authority boundary

Free windows are advisory context only. They are not Tasks, Calendar events, reservations, availability promises, or time blocks. This tranche does not:

- create or modify a task;
- reschedule a task;
- create or modify a Calendar event;
- add a task-duration persistence model;
- reserve time;
- infer event purpose/content;
- make Calendar optional context a dependency for ordinary Tasks workflows; or
- authorize a user-facing automatic scheduling action.

## Platform boundary

Calendar remains authoritative for event authorization and busy-time derivation. Tasks remains authoritative for task content and lifecycle. The development bearer/principal pairing remains transitional and is not production GoreeCloud Identity delegation. No new Mesh authority, Privacy Shield acceptance, Wardveil Security acceptance, Everkeep state, deployment, release, or Stable qualification is created by this pure planning step.
