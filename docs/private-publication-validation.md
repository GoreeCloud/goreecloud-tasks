# Private Publication Validation

## Purpose

This document records the source-controlled, non-activating private-publication validation for GoreeCloud Tasks.

The production target remains `https://tasks.goreecloud.com`, with the approved GoreeCloud private-service path:

1. approved NetBird client;
2. private DNS through AdGuard Home;
3. Caddy HTTPS termination and source restriction;
4. Docker proxy-network communication to GoreeCloud Tasks; and
5. application authentication and authorization.

The disposable validation intentionally does not create or modify real AdGuard Home rewrites, NetBird peers/groups/policies, Porkbun DNS records, Caddy production configuration, firewall rules, or a production Tasks deployment.

## Governing Publication Rules Exercised

The validation mirrors the GoreeCloud private-publication requirements that are safe to reproduce in disposable CI:

- the user-facing hostname is exactly `tasks.goreecloud.com`;
- Caddy is the HTTPS reverse proxy;
- approved source traffic is modeled inside `100.64.0.0/10`;
- a source outside that range receives an explicit HTTP 403 denial;
- a client-controlled `X-Forwarded-For` value cannot bypass the source restriction;
- Tasks is reachable by Caddy only over a Docker proxy network;
- PostgreSQL remains on a separate internal backend network;
- approved and unapproved client networks cannot directly resolve the Tasks backend or database;
- Tasks and PostgreSQL publish no host ports; and
- application authentication remains required after the private network boundary succeeds.

## Disposable Topology

The validation stack is defined in `scripts/private_publication.compose.yml`.

It contains:

- PostgreSQL on an internal `backend` network;
- GoreeCloud Tasks on `backend` and `proxy`, using the stable Docker alias `goreecloud-tasks`;
- Caddy on `proxy`, `approved_ingress`, and `unapproved_ingress`;
- an approved synthetic client at `100.100.0.10`, which is inside the NetBird CGNAT range `100.64.0.0/10`; and
- an unapproved synthetic client at `172.30.240.10`, outside the NetBird range.

All disposable networks are Docker-internal networks. No service in this CI topology publishes a host port.

The Caddy image is pinned to official Caddy 2.11.4 by digest. The production GoreeCloud Caddy image may include additional approved plugins such as the Porkbun DNS provider; the disposable gate does not require that plugin because it does not contact a public certificate authority.

## TLS Boundary

`scripts/private_publication.Caddyfile` uses `tls internal` only for disposable validation.

This allows the gate to prove:

- TLS negotiation occurs at Caddy;
- the served certificate contains the exact `tasks.goreecloud.com` DNS subject alternative name; and
- HTTPS requests for the approved hostname reach the intended reverse-proxy route.

The client intentionally does not treat the disposable Caddy internal CA as publicly trusted.

Production still requires the approved Porkbun DNS-01 workflow and a publicly trusted certificate for `tasks.goreecloud.com`. This CI gate does not claim that production certificate issuance has been completed.

## Application Security on the Proxy Path

The disposable Tasks service runs with production-oriented settings for the publication path:

- `DJANGO_DEBUG=false`;
- `DJANGO_ALLOWED_HOSTS=tasks.goreecloud.com`;
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://tasks.goreecloud.com`;
- secure cookies enabled; and
- HTTPS redirect behavior enabled while trusting Caddy's `X-Forwarded-Proto` through the existing `SECURE_PROXY_SSL_HEADER` setting.

The validation requires:

- `/health/` to return HTTP 200 through Caddy for the approved source;
- an unauthenticated request to `/` to redirect to the Django login flow rather than expose task content;
- the login response to include a CSRF token and a `Secure` CSRF cookie; and
- no `DisallowedHost`, invalid-host, or CSRF-verification errors in the disposable application logs.

## Fail-Closed Checks

The gate fails when any of the following occurs:

- a service gains a host-published port;
- network memberships drift from the intended least-privilege topology;
- the approved client leaves the synthetic NetBird range;
- the unapproved client enters that range;
- the unapproved client receives anything other than HTTP 403;
- spoofing `X-Forwarded-For` bypasses the Caddy source restriction;
- an approved client can directly resolve `goreecloud-tasks` or `db`;
- Caddy cannot reach the Tasks backend by the stable Docker alias;
- TLS no longer presents the exact private hostname;
- application authentication no longer protects the main interface;
- secure CSRF cookie behavior is lost; or
- disposable database or Django secret values appear in rendered Compose, Docker inspection data, or stack logs.

## Relationship to Runtime Security Preflight

The Runtime Security Preflight and Private Publication Validation cover different layers.

Runtime Security Preflight proves non-root application execution, file-backed secret permissions, capability and privilege restrictions, build-context exclusion, internal database networking, and related container controls.

Private Publication Validation proves the user-facing Caddy/private-client boundary and confirms that adding a reverse proxy does not broaden backend or database exposure.

Both are disposable evidence gates. Neither is a substitute for inspecting the actual Infrastructure Services VM before production approval.

## Production Evidence Still Required

Before `tasks.goreecloud.com` is approved for production use, the actual target environment still requires direct validation of:

- AdGuard Home private DNS rewrite behavior from an approved client;
- real NetBird peer, group, and least-privilege access-policy state;
- the active Caddy production site block;
- Porkbun DNS-01 certificate issuance and the publicly trusted certificate chain;
- exact Caddy host listener and port ownership;
- host firewall behavior;
- backend and database runtime port exposure on the real Docker host;
- live application authentication, authorization, and multi-user privacy through the production route;
- production logs and monitoring;
- production backup and recovery controls; and
- rollback of the publication path.

No production publication is approved or activated by this validation alone.
