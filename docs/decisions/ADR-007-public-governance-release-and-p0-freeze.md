# ADR-007: Public governance, compatibility, release policy, and P0 final freeze

- Status: Proposed
- Date: 2026-06-28
- Parent architecture Issue: #25
- Decision Issue: #49

## Context

LingShu has accepted the technical architecture needed to begin implementation. P0 cannot freeze until the repository also defines its license, contribution and conduct rules, security reporting, compatibility and release semantics, first development version, P1 scope, and explicit authorization boundary.

## Decision

### License

LingShu is licensed under Apache License 2.0.

The repository includes:

```text
LICENSE
NOTICE
```

Package metadata uses the SPDX identifier `Apache-2.0` after P1 creates `pyproject.toml`. Required third-party attribution is appended to NOTICE. License changes require a dedicated Issue, legal/compatibility review, and project-lead approval.

### Contributions

LingShu uses Developer Certificate of Origin 1.1.

- every commit requires a `Signed-off-by` trailer;
- `git commit -s` is the normal workflow;
- unsigned commits block merge until corrected;
- no Contributor License Agreement is required initially;
- contributions are accepted under Apache-2.0 unless explicitly and validly designated otherwise before submission;
- one Issue/branch/primary writer/worktree/environment/PR remains mandatory;
- final merge authority remains with the project lead.

### Code of Conduct

The project adopts a LingShu-specific policy adapted from Contributor Covenant 2.1. It applies in public and private official project spaces and includes confidential reporting, conflict-of-interest handling, and proportionate enforcement.

### Security

Private vulnerability reporting is required before the first public release.

- use GitHub Private Vulnerability Reporting as the preferred channel;
- never publish unpatched exploit details in public Issues/PRs;
- acknowledge credible reports within a best-effort target of 3 business days;
- initial triage target is 7 business days;
- provide material updates at least every 14 days while remediation remains active;
- coordinate disclosure and preserve reporter credit/preferences;
- publish advisories, changelog entries, and mitigation/migration instructions when appropriate.

Before 1.0, only the latest `0.y` minor line is supported unless otherwise announced. After 1.0, the current major's latest minor is supported, and the previous major normally receives critical/high-severity fixes for 180 days after a new major.

### Versioning

LingShu follows Semantic Versioning 2.0.0, refined by project compatibility rules.

First P1 development version:

```text
0.1.0.dev0
```

Tags use `vX.Y.Z` and corresponding prerelease forms. Package versions do not include the `v` prefix.

Released versions and artifacts are immutable.

### Pre-1.0 compatibility

Patch releases inside one `0.y` line are backward compatible except for narrowly approved security/correctness emergencies.

Breaking public changes:

- require a new `0.(y+1).0` minor release;
- must be explicit in changelog/release notes;
- require migration guidance and contract-test updates;
- should be deprecated for at least one released minor where practical.

Major version zero does not authorize undocumented arbitrary breakage.

### Compatibility after 1.0

- patch: backward-compatible fixes;
- minor: backward-compatible features and deprecations;
- major: incompatible public changes.

Normal removal requires at least two released minor versions and 180 days of deprecation. Security, data-corruption, protocol-ambiguity, privilege, or severe correctness exceptions may shorten the window with project-lead approval and explicit documentation.

### Public API boundary

Public API includes only documented/exported names, documented CLI/configuration/wire contracts, and stable error codes. Importable private implementation is not automatically public.

### Branch and release model

- `main` is the only long-lived development/integration branch;
- no long-lived `develop`;
- work uses short-lived Issue branches;
- `release/X.Y` is allowed only as a short-lived stabilization branch;
- release fixes merge back to `main`;
- release PR updates version and changelog but does not publish before merge;
- an annotated tag triggers protected CI artifact build;
- authoritative artifacts are built from the tag by CI;
- tag/version/metadata/changelog/release notes must agree;
- failed releases are yanked/superseded, never overwritten;
- no auto-merge.

### Publication credentials and provenance

Before public package-index publication:

- use short-lived identity-based trusted publishing where supported;
- do not store a long-lived production package-index token in CI;
- generate and retain artifact hashes and verifiable provenance/attestation;
- separate staging/test publication from production publication;
- only the project lead authorizes production publication.

### Changelog

`CHANGELOG.md` uses:

```text
Added
Changed
Deprecated
Removed
Fixed
Security
```

User-visible PRs update `Unreleased`. Released sections are dated and immutable in substance; corrections are explicit. Embargoed security entries remain private until coordinated disclosure.

### P1 scope

P1 is the single-Worker minimum vertical slice described in `docs/development/P1_IMPLEMENTATION_PLAN.md`.

P1 includes package/CI foundations, core primitives, runtime Scope/Deadline/cancellation, HTTP model, Router/Middleware, Application Kernel, minimum Runtime Record, single-Worker HTTP/1.1 Server, CLI `version/check/run --workers 1`, and clean artifact installation.

P1 excludes multi-Worker Supervisor, file reload, production configuration reload, advanced streaming/body formats, official extensions, and public PyPI production release.

### P1 dependency graph

P1 uses symbolic Issues P1-00 through P1-10, with provider-first serial integration and limited non-overlapping parallel waves.

No implementation Issue may begin before Final Freeze. The exact GitHub Issues are created only after the dedicated Final Freeze PR is merged.

### P0 Freeze Candidate

Merging the P0-D7 decision PR:

- accepts the governance proposal for finalization;
- creates a P0 Freeze Candidate;
- does not authorize production implementation;
- keeps ADR-007 and Blueprint status pending final synchronization.

A separate Final Freeze PR must:

1. mark ADR-007 Accepted;
2. mark the Blueprint Frozen;
3. verify ADR-001 through ADR-007 and all control documents agree;
4. close parent Issue #25 as completed;
5. record the final P0 merge commit;
6. mark `CURRENT_PHASE` as P1 authorized;
7. authorize creation of P1 Issues and production package files;
8. state that project-lead merge is the explicit P1 authorization.

Only merger of that Final Freeze PR ends P0.

## Required governance tests/checks

Before Final Freeze, verify:

- LICENSE is the unmodified Apache License 2.0 text;
- NOTICE and package-license metadata are consistent;
- CONTRIBUTING references DCO and requires sign-offs;
- DCO text is unmodified;
- security reporting contains a private path and no invented public mailbox;
- supported-version rules agree across SECURITY and release policy;
- Code of Conduct has private reporting and conflict handling;
- changelog categories and version rules agree;
- Blueprint contains no Proposed technical decision from P0-D1 through D7;
- no second architecture source conflicts with the Blueprint;
- P1 plan respects accepted package/ownership/dependency boundaries;
- no production source, package skeleton, dependency, or workflow exists before Final Freeze.

## Rejected alternatives

- no license or placeholder license metadata;
- initial proprietary/non-open-source licensing;
- MIT-only proposal without the selected Apache-2.0 terms;
- CLA requirement for ordinary initial contributions;
- unsigned contributions without DCO;
- public vulnerability Issues as the primary channel;
- treating all 0.x patch releases as freely breaking;
- modifying released artifacts in place;
- long-lived `develop`;
- workstation-built authoritative releases;
- long-lived package-index credentials in CI;
- automatic P1 start merely because a proposal PR merged;
- broad P1 implementation of multi-Worker, reload, extensions, and advanced protocols before a single-Worker vertical slice.

## Intentionally deferred

- exact first public release date;
- exact public package-index project creation timing;
- manual cryptographic signature scheme beyond required provenance/attestation;
- trademark registration and separate trademark policy;
- paid support or enterprise support terms;
- post-1.0 long-term-support branches;
- public governance bodies beyond the project lead/contributors;
- actual P1 code and CI implementation.
