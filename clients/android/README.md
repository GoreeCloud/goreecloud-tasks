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
- a truthful capability surface that distinguishes source-ready API/Identity contracts from blocked/not-implemented runtime features;
- a pure fail-closed Identity acceptance-proof policy for exact principal/audience/lifetime metadata;
- a repository-local Android adaptation target for current Stable GLAZE UI V1.4 / `1.4.0`;
- unit coverage preventing the shell from advertising identity, remote reads, cache, mutation, or background sync as available.

## GoreeCloud Identity source-contract boundary

The Tasks client now aligns its non-secret acceptance metadata with GoreeCloud Identity schema `goreecloud.identity.native-application-session/v1`, pinned to Development candidate revision `62ad109809f2e479cf71a6327ffd0d4537a6b3df`.

That Identity candidate currently defines the common proof metadata as exact `principalId`, exact registered audience, `issuedAt`, and exclusive `expiresAt`, with no string normalization, no future-issued proof acceptance, and independent consumer acceptance. Tasks uses the Development consumer audience `goreecloud-tasks-android` as a local expectation only; this does **not** claim that a production Identity application registration or accepted runtime exists.

A successful local `TasksIdentityBindingPolicy` decision means only that supplied non-secret metadata is internally consistent with the expected principal, audience, and lifetime. It is not a bearer credential, does not authenticate a user by itself, and cannot bypass the server's existing `visible_to(user)` or `editable_by(user)` authorization rules.

The Identity proof contract is therefore `SOURCE_READY`, while the actual native Identity/session exchange remains `BLOCKED`.

## Deliberate restrictions

The first APK does **not** declare `INTERNET`. The server-side Development API currently authenticates through the existing GoreeCloud Tasks web user session, while the native-client API contract explicitly leaves GoreeCloud Identity/session exchange as a follow-on milestone. This client therefore does not invent bearer credentials, embed reusable service secrets, copy browser cookies, or silently bypass that boundary.

The client also does not create a second authoritative task database. Local persistence, incremental synchronization, offline mutation queues, reminders, notifications, widgets, and write APIs remain blocked until their server-side conflict, revocation, recovery, and authorization contracts are accepted.

## GLAZE UI V1.4 boundary

The application targets current Stable GLAZE UI V1.4 from the beginning. Reading and explicit decision surfaces are solid; transient chrome remains bounded. No environmental sensing, telemetry, camera context, remote optical context, or decorative memory source is introduced.

`GlazeTasksTheme` is a repository-local Android adaptation shell, **not** evidence that native V1.4 conformance has been accepted. Native Optical Engine mapping, reduced-transparency behavior, increased-contrast behavior, accessibility acceptance, physical-device review, and V1.4.1 human verification remain separate gates.

## Next implementation order

1. Implement and accept the GoreeCloud Identity native session/runtime that can produce the canonical proof metadata for a registered Tasks audience.
2. Add authenticated read-only network transport with private/no-store semantics preserved end to end.
3. Parse and render list/detail schemas without broadening server authorization.
4. Add protected local caching only with revocation and incremental-sync behavior defined.
5. Add mutations only after conditional/version conflict semantics are accepted.
6. Add background sync, reminders, notifications, and widgets after runtime authority is accepted.
7. Complete repository-local GLAZE UI V1.4 native acceptance plus Wardveil, Privacy Shield, Everkeep, representative-device, accessibility, signing/provenance, and release validation.

No source/build/emulator result by itself makes GoreeCloud Tasks Android Stable or production-approved.
