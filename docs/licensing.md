# GoreeCloud Tasks Licensing

## Decision

GoreeCloud Tasks uses the **GNU Affero General Public License v3.0 only** (`AGPL-3.0-only`).

This is an intentional project-level licensing decision for the original GoreeCloud Tasks application. The complete license text is stored in the repository root as `LICENSE`, and the project-specific copyright and version-selection notice is stored in `LICENSE-NOTICE.md`.

## Why AGPL-3.0-only

GoreeCloud Tasks is a self-hosted, network-served multi-user web application. A strong network-aware copyleft license best matches the project's long-term objectives for source availability, independent operation, modification, redistribution, and resistance to a modified hosted version becoming effectively closed source.

The GNU Affero General Public License specifically adds a remote-network source requirement for modified versions used to provide network service. That characteristic is directly relevant to GoreeCloud Tasks because its normal operating model is a web application accessed through a network.

The `-only` form is used instead of `AGPL-3.0-or-later` so the repository remains governed by the exact license version reviewed and approved for the project. A future change to another license version would require a separate deliberate licensing decision rather than occurring automatically.

## Current Direct Dependency Review

The current direct Python dependencies remain separately licensed and are not relicensed by GoreeCloud Tasks:

- Django 5.2.17 — BSD 3-Clause license.
- Gunicorn 26.0.0 — MIT License.
- Psycopg 3.3.4 — LGPL-3.0-only.

These licenses permit their continued use as dependencies of the AGPL-licensed GoreeCloud Tasks application under the current architecture. Any future dependency must still receive its own licensing review before adoption.

## Repository Requirements

The repository must retain:

- `LICENSE` containing the verbatim GNU Affero General Public License version 3 text;
- `LICENSE-NOTICE.md` identifying `AGPL-3.0-only`, the project copyright holder, and the project-specific licensing boundary;
- required third-party copyright, attribution, and license notices when applicable; and
- accurate documentation that distinguishes GoreeCloud Tasks licensing from dependency licensing.

Material source distributions must preserve the applicable license and copyright notices. Modifications should be documented as required by the governing license.

## Network Source Availability

Before a public GoreeCloud Tasks service or public release is approved, the user interface and release documentation should provide a clear **Source** or **License / Source** path appropriate to the running version.

A modified version operated as a network service must provide users interacting with that version an opportunity to obtain its Corresponding Source as required by AGPL section 13.

The source-access requirement is a licensing obligation and does not replace GoreeCloud's separate requirements for privacy, authentication, authorization, deployment security, backups, monitoring, or service publication.

## Public Release Boundary

Adding the open-source license removes the project's licensing blocker, but it does not make GoreeCloud Tasks production-ready and does not authorize:

- making the private GitHub repository public;
- deploying GoreeCloud Tasks to production;
- publishing `tasks.goreecloud.com`;
- changing DNS, Caddy, NetBird, or firewall configuration;
- provisioning production ntfy credentials or scheduler infrastructure; or
- declaring the application stable or generally available.

Those actions remain controlled by the project specification and the outstanding production-readiness acceptance requirements.

## Future License Changes

A future license change must be deliberate, documented, and reviewed for contributor copyright ownership, dependency compatibility, downstream obligations, and the effect on previously released versions. Previously distributed releases remain governed by the license terms under which they were released unless all required rights permit a lawful relicensing action.
