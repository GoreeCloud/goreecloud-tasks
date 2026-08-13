# Monitoring and Alert-Delivery Readiness

## Purpose

This document records the source-controlled, non-activating monitoring and alert-delivery readiness validation for GoreeCloud Tasks.

The production application is still not approved for deployment. This validation does not create a real Uptime Kuma monitor, change the production Caddyfile, register a production notification route, install a token, alter a Vaultwarden item, or send messages through the production ntfy service.

## Approved Monitoring Roles

GoreeCloud uses Uptime Kuma as the primary service-availability and endpoint-monitoring platform. Healthchecks is used for scheduled jobs, expected heartbeats, and missed execution windows.

For GoreeCloud Tasks, the primary availability signal is therefore the HTTPS application health endpoint:

`https://tasks.goreecloud.com/health/`

The proposed source-controlled monitor contract is stored in `scripts/tasks_uptime_kuma_monitor.json`.

The contract is deliberately marked `proposed-not-provisioned`. It records the monitor values that can already be justified from the application and infrastructure design while leaving deployment-specific values such as retries, retry interval, timeout, the live Uptime Kuma notification assignment identifier, and final source-address observation for direct target-host validation.

## Uptime Kuma Source Identity

The current GoreeCloud proxy-network inventory assigns Uptime Kuma the fixed Docker address `172.19.0.50`. GoreeCloud private Caddy routes already use that stable source identity where Uptime Kuma must monitor a private HTTPS endpoint.

The disposable monitoring fixture therefore models the intended Tasks publication rule as:

- approved NetBird clients in `100.64.0.0/10`; and
- the dedicated Uptime Kuma monitoring source `172.19.0.50`.

The fixture does not modify the real GoreeCloud Caddyfile. The final Tasks production site block must be inspected and approved separately before deployment.

## Notification Boundary

The existing GoreeCloud ntfy strategy assigns:

- service identity: `uptime-kuma`;
- topic: `goreecloud-uptime`;
- permission: write-only; and
- preferred internal server URL: `http://ntfy:80`.

The monitoring readiness gate reproduces that boundary with disposable identities and runtime-random tokens. The publisher can publish to `goreecloud-uptime` but cannot subscribe. A disposable administrative subscriber can read the topic but cannot publish. Anonymous reads are denied.

No reusable production token is stored in source, output, logs, or documentation.

## Disposable Topology

`scripts/monitoring_alert.compose.yml` creates a temporary topology containing:

- PostgreSQL on an internal backend network;
- GoreeCloud Tasks on backend and proxy networks;
- Caddy on the proxy network with the `tasks.goreecloud.com` alias;
- a hardened disposable ntfy server on the proxy network;
- a synthetic Uptime Kuma monitor client fixed at `172.19.0.50`; and
- a read-only subscriber used only to verify delivered alert state.

Only the monitoring source uses a fixed proxy address because that source identity is the access-control fact under test. Disposable Caddy and application addresses are allowed to be dynamically assigned so migration or startup helper containers cannot collide with an unnecessary fixed test address.

No service publishes a host port.

The Caddy fixture uses `tls internal`. The monitor mounts the disposable Caddy root CA read-only so the HTTPS probe performs certificate-chain and hostname verification instead of disabling TLS verification.

This is intentionally stronger than accepting an insecure test certificate while still avoiding public DNS or certificate-authority changes.

## State-Transition Validation

The gate validates the monitoring lifecycle rather than only checking that `/health/` exists.

### Healthy State

The monitor must successfully reach `https://tasks.goreecloud.com/health/` through Caddy with verified TLS and receive HTTP 200 plus the expected `{"status": "ok"}` payload.

The subscriber must confirm that no alert was generated solely because the service was healthy.

### Outage State

The validator stops the disposable Tasks web service while leaving Caddy and ntfy running.

The synthetic monitor must observe a server-side failure through the same HTTPS hostname. Only after detecting that failure may it publish the sanitized transition:

- title: `GoreeCloud Tasks DOWN`;
- message: `GoreeCloud Tasks health endpoint is unavailable. Review Uptime Kuma and protected service logs.`

The subscriber must receive exactly that DOWN transition.

### Recovery State

The validator restarts Tasks and waits for its application health check to pass.

The monitor must again receive the expected HTTPS health response and then publish:

- title: `GoreeCloud Tasks RECOVERED`;
- message: `GoreeCloud Tasks health endpoint recovered.`

The subscriber must observe the ordered DOWN then RECOVERED transition sequence.

## Data Minimization

Alert bodies intentionally identify only the affected application and the operational state.

Messages must not contain:

- passwords;
- access tokens;
- database credentials;
- Django secret keys;
- authentication headers;
- session identifiers;
- CSRF values;
- environment-file contents; or
- protected log contents.

The validator additionally scans rendered Compose data, Docker inspection data, and stack logs for all disposable database, Django, publisher, and subscriber secret values.

## Relationship to Healthchecks

No permanent Healthchecks check is proposed for ordinary Tasks endpoint availability in this increment.

Healthchecks remains appropriate for future scheduled Tasks operations when a successful execution heartbeat is the signal being monitored, such as a scheduled production backup, periodic maintenance job, or another time-bounded task. Those checks require their own schedule, grace period, integration, and production approval.

This distinction avoids duplicating endpoint availability monitoring in two platforms without a defined operational reason.

## Self-Monitoring and Failure-Domain Limitation

ntfy is a notification-delivery service, not the monitoring authority. Uptime Kuma remains responsible for determining endpoint state.

The disposable gate proves that a Tasks outage can be detected and that a separate healthy ntfy service can carry DOWN and recovery notifications.

It does not prove independent alert delivery when ntfy itself is unavailable. The GoreeCloud ntfy strategy explicitly recognizes that a self-hosted ntfy server cannot reliably deliver its own outage notification through itself.

An out-of-band notification path remains separately required before claiming independent ntfy-down alert delivery for critical monitoring.

## Production Evidence Still Required

Before Tasks monitoring may be considered production-ready, direct target-environment evidence must confirm at minimum:

1. the actual Tasks deployment is healthy on the Infrastructure Services VM;
2. the final production Caddy site block allows the intended Uptime Kuma source without broadening access to unrelated Docker sources;
3. the live Uptime Kuma source is still the approved fixed identity and is observed by Caddy as intended;
4. Uptime Kuma is configured to monitor `https://tasks.goreecloud.com/health/` rather than a direct backend URL;
5. TLS verification remains enabled against the publicly trusted production certificate;
6. the final retry count, retry interval, request timeout, and accepted status-code behavior are reviewed and recorded;
7. the existing `uptime-kuma` ntfy identity remains write-only to `goreecloud-uptime`;
8. its reusable token is retrieved from the approved protected location without being written to source or ordinary documentation;
9. an approved administrative subscriber receives a controlled real DOWN/recovery validation message;
10. Uptime Kuma records outage and recovery history correctly;
11. alert content remains data-minimized and contains no reusable secrets or private task content;
12. monitor removal and notification-route rollback are documented; and
13. any required independent notification path is separately deployed and tested before claiming cross-failure-domain alert delivery.

## Production Boundary

This source-controlled increment does not:

- create a real Uptime Kuma monitor;
- alter the current Uptime Kuma database or Compose stack;
- change the production Uptime Kuma fixed address;
- change the production Caddyfile;
- add a production Caddy source allowlist entry;
- change AdGuard Home, Porkbun, NetBird, firewall, or DNS state;
- create or rotate the Uptime Kuma ntfy token;
- modify Vaultwarden;
- change production ntfy ACLs, topics, users, or subscribers;
- create a Healthchecks check;
- register a production monitor in Manager;
- deploy GoreeCloud Tasks; or
- activate production monitoring.

Production remains separately approval-controlled.
