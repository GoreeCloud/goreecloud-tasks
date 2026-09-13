# GoreeCloud Tasks Android

**Status:** Development foundation  
**Authoritative task model:** GoreeCloud Tasks server/web data and authorization model  
**Native API:** `/api/v1/client/`  
**Glaze UI target:** `1.4.0` at `84cb3db4884042f0fa25ed6d475a127fb110f596`

This directory establishes the first native Android GoreeCloud Tasks application foundation after the read-only native API contract became available.

## Current implementation

The Android module currently provides:

- a compilable first-party Compose application;
- pure Kotlin construction and validation for the accepted native list/detail endpoint family;
- client-side enforcement of the documented `state`, `status`, `project`, and `limit` bounds;
- a truthful capability surface that distinguishes source-ready API contracts from blocked/not-implemented runtime features;
- a repository-local Android adaptation target for current Stable GLAZE UI V1.4 / `1.4.0`;
- unit coverage preventing the shell from advertising identity, remote reads, cache, mutation, or background sync as available.

## Deliberate restrictions

The first APK does **not** declare `INTERNET`. The server-side Development API currently authenticates through the existing GoreeCloud Tasks web user session, while the native-client API contract explicitly leaves GoreeCloud Identity/session exchange as a follow-on milestone. This client therefore does not invent bearer credentials, embed reusable service secrets, copy browser cookies, or silently bypass that boundary.

The client also does not create a second authoritative task database. Local persistence, incremental synchronization, offline mutation queues, reminders, notifications, widgets, and write APIs remain blocked until their server-side conflict, revocation, recovery, and authorization contracts are accepted.

## GLAZE UI V1.4 boundary

The application targets current Stable GLAZE UI V1.4 from the beginning. Reading and explicit decision surfaces are solid; transient chrome remains bounded. No environmental sensing, telemetry, camera context, remote optical context, or decorative memory source is introduced.

`GlazeTasksTheme` is a repository-local Android adaptation shell, **not** evidence that native V1.4 conformance has been accepted. Native Optical Engine mapping, reduced-transparency behavior, increased-contrast behavior, accessibility acceptance, physical-device review, and V1.4.1 human verification remain separate gates.

## Next implementation order

1. Define and accept GoreeCloud Identity/session exchange for first-party native clients.
2. Add authenticated read-only network transport with private/no-store semantics preserved end to end.
3. Parse and render list/detail schemas without broadening server authorization.
4. Add protected local caching only with revocation and incremental-sync behavior defined.
5. Add mutations only after conditional/version conflict semantics are accepted.
6. Add background sync, reminders, notifications, and widgets after runtime authority is accepted.
7. Complete repository-local GLAZE UI V1.4 native acceptance plus Wardveil, Privacy Shield, Everkeep, representative-device, accessibility, signing/provenance, and release validation.

No source/build/emulator result by itself makes GoreeCloud Tasks Android Stable or production-approved.
