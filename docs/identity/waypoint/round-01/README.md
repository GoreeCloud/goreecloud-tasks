# GoreeCloud Waypoint Visual Identity — Round 01

Status: **Unapproved review candidates only**

No asset in this directory is the canonical Waypoint identity. Nothing in this round is approved for application launchers, production UI, public websites, package metadata, favicons, GoreeCloud Manager, documentation outside this review context, or other production-facing use until an exact candidate and its recorded source bytes are explicitly approved.

The governing identity remains **GoreeCloud Waypoint**, the capability system within GoreeCloud Tasks. The visual direction must communicate direction, progress, destination, navigation, or coordinated movement without reducing Waypoint to a generic map-pin symbol.

## Candidate A — Route Orbit

![Route Orbit](./route-orbit.svg)

A curved route passes through multiple checkpoints before reaching a forward destination. This concept emphasizes the Waypoint ideas of route, progress, intermediate milestones, and movement toward completion.

Review priorities: small-size recognition, distinction from generic navigation apps, clarity of the three-checkpoint story, monochrome adaptability, and visual compatibility with GoreeCloud Tasks.

## Candidate B — Compass Lane

![Compass Lane](./compass-lane.svg)

A directional lane moves through a navigational ring. This concept emphasizes orientation, planning, and maintaining direction while preserving a stronger abstract identity than a literal compass or map pin.

Review priorities: avoid reading as a generic compass utility, retain the forward-motion lane at favicon scale, preserve balance in dark/light contexts, and remain distinguishable from Network or DNS identity concepts.

## Candidate C — Progress Meridian

![Progress Meridian](./progress-meridian.svg)

Multiple paths converge on one destination. This concept emphasizes coordinated work, prioritization, alternate routes, and measurable progress toward completion.

Review priorities: avoid resembling an analytics chart, preserve convergence at small sizes, maintain clear destination symbolism, and remain recognizable in monochrome treatment.

## Mandatory Review Criteria

Before any candidate can become canonical, review the exact source asset for:

- semantic fit with GoreeCloud Waypoint and GoreeCloud Tasks;
- originality and separation from existing GoreeCloud identities;
- recognition at 512, 192, 48, 32, and 16 pixel presentation sizes;
- light, dark, reduced-color, and monochrome behavior;
- sufficient contrast and simple geometry at small sizes;
- Glaze UI family coherence without making Waypoint visually interchangeable with another product;
- avoidance of generic map-pin, checkmark-only, letter-only, or ordinary productivity-app symbolism;
- suitability as a capability mark that complements rather than replaces the canonical GoreeCloud Tasks application identity;
- exact-source approval before any derivative-generation or production integration work begins.

## Governance Boundary

`manifest.json` records this round as `unapproved-review-only`, sets `canonical_identity` to `null`, and binds each concept to a SHA-256 digest. Approval must identify the exact candidate and exact source digest. Technical source validation does not constitute visual approval.

If no candidate is satisfactory, this round should remain historical review material and a new materially different round should be created rather than silently editing an approved asset into existence.
