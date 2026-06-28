# LingShu Release and Compatibility Policy

- Status: Accepted when PR #51 is merged
- Parent architecture Issue: #25 (closed by PR #51)
- Decision Issue: #49 (closed by PR #51)
- Related ADR: `docs/decisions/ADR-007-public-governance-release-and-p0-freeze.md`
- Final Freeze: PR #51

## 1. Version model

LingShu follows Semantic Versioning 2.0.0:

```text
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

Tags use:

```text
vMAJOR.MINOR.PATCH
vMAJOR.MINOR.PATCH-prerelease
```

Package metadata omits the `v` prefix. A published version and its artifacts are immutable; corrections require a new version.

## 2. First development version

The first P1 package skeleton uses:

```text
0.1.0.dev0
```

This is a development version, not a public stable release. Future prereleases may use:

```text
0.1.0a1
0.1.0b1
0.1.0rc1
```

The first normal public release is `0.1.0` only after its acceptance gate passes and the project lead separately authorizes publication.

## 3. Public API definition

Public API consists only of:

- names explicitly exported by documented public modules;
- behavior explicitly promised in user documentation;
- documented CLI commands and options;
- documented configuration and wire contracts;
- documented stable error codes;
- documented package metadata and configuration keys.

Importable implementation details are not automatically public. The root facade is controlled through explicit export manifests; deep modules remain private unless documentation promotes them.

## 4. Pre-1.0 compatibility

### Patch releases: `0.Y.Z`

Patch releases remain backward compatible inside the same minor line except for a narrowly approved security or severe correctness emergency.

Allowed patch changes include:

- bug fixes;
- compatible performance improvements;
- documentation and diagnostics corrections;
- private implementation changes;
- non-breaking security fixes.

A patch release must not silently remove or alter a documented public API.

### Minor releases: `0.Y.0`

A pre-1.0 minor release may contain breaking public changes, but each breaking change must:

- appear in changelog and release notes;
- include migration guidance;
- explain why compatibility could not be preserved;
- update public export manifests and contract tests;
- avoid unrelated breakage.

Where practical, removal is preceded by at least one released minor that marks the API deprecated.

Major version zero does not permit undocumented arbitrary breakage.

## 5. Version 1.0 and later

After `1.0.0`:

- PATCH contains backward-compatible fixes;
- MINOR contains backward-compatible features and deprecations;
- MAJOR contains incompatible public changes.

Normal public API removal requires at least:

```text
two released minor versions
AND
180 days
```

Removal occurs in a new major version unless an approved security/correctness exception applies.

## 6. Deprecation contract

A deprecation provides:

- deprecated symbol or behavior;
- replacement or migration path;
- release where deprecation begins;
- earliest eligible removal release and time;
- user-visible warning where appropriate;
- documentation and changelog entries;
- tests preserving deprecated behavior during the window.

Warnings must be actionable, bounded, and free of secrets or high-cardinality data.

## 7. Emergency compatibility exceptions

Security, data corruption, protocol ambiguity, privilege-boundary failure, audit failure, or severe correctness defects may require immediate incompatible action.

An emergency exception must:

- be the narrowest safe change;
- be approved by the project lead;
- include an advisory or incident explanation when disclosure permits;
- document affected versions and migration/mitigation;
- use an appropriate version bump;
- never rewrite existing artifacts.

## 8. Branch model

Long-lived branch:

```text
main
```

Rules:

- `main` is the only long-lived development/integration branch;
- no long-lived `develop`;
- normal work uses short-lived Issue branches;
- release stabilization may use short-lived `release/X.Y` only when necessary;
- security/hotfix branches are short-lived and merge back to `main`;
- final merge authority belongs to the project lead;
- automatic merge is prohibited.

## 9. Release preparation

A release PR must:

1. select a version from the accepted change set;
2. update static `[project].version` as the single version source;
3. move relevant `Unreleased` entries into a dated release section;
4. update support/security tables when required;
5. include migration notes for incompatible changes;
6. pass the full release matrix;
7. build wheel and sdist from a clean checkout;
8. inspect metadata, LICENSE, NOTICE, and artifact inventory;
9. install and test artifacts outside the checkout;
10. verify tag/version/changelog consistency.

The release PR does not publish artifacts before merge.

## 10. Tagging and artifact construction

After a release PR merges:

```text
main release commit
→ annotated tag vX.Y.Z
→ protected CI build from tag
→ test and inspect artifacts
→ produce provenance/attestation
→ publish release notes and artifacts
→ publish to package index when separately authorized
```

Authoritative artifacts come from CI from the tag, not from a developer workstation.

Tag, project version, wheel metadata, sdist metadata, GitHub release, and changelog must agree.

## 11. Package-index publication

Before the first public package-index release:

- configure short-lived identity-based trusted publishing where supported;
- do not store a long-lived production package-index password or API token in CI;
- separate test/staging publication from production publication;
- require explicit project-lead authorization.

Final Freeze authorizes P1 implementation, not public package publication.

## 12. Signing and provenance

The release pipeline preserves:

- source commit and tag identity;
- workflow identity;
- artifact hashes;
- build environment and tool versions;
- test results;
- platform-supported provenance or attestation.

Manual signing may be added later. Absence of manual signature must not be confused with absence of provenance.

## 13. Failed release and rollback

Published artifacts are never overwritten or silently replaced.

When a release is defective:

- stop promotion/deployment where possible;
- publish a new corrected version;
- yank the defective package-index release when appropriate without deleting history;
- identify the affected release in release notes or an advisory;
- provide mitigation and upgrade guidance;
- preserve evidence and artifact hashes;
- merge fixes back to `main`.

Deleting or retargeting a publicly released tag is prohibited. An unpublished private mistake may be corrected only with project-lead approval and explicit documentation.

## 14. Changelog policy

`CHANGELOG.md` records notable user-visible changes under:

```text
Added
Changed
Deprecated
Removed
Fixed
Security
```

Rules:

- user-visible PRs update `Unreleased` unless explicitly exempted;
- internal refactors without observable effect may omit entries;
- security entries may remain embargoed until coordinated disclosure;
- breaking changes include migration guidance;
- released sections are dated;
- release notes may add detail but cannot contradict the changelog.

## 15. Security support policy

Before 1.0, only the latest `0.y` minor line is supported unless otherwise announced.

After 1.0, the latest minor of the current major is supported. After a new major, the previous major normally receives critical/high-severity fixes for 180 days.

Exact supported versions are maintained in `SECURITY.md` and release notes.

## 16. Dependency and platform changes

A new mandatory runtime dependency requires a dedicated dependency review or ADR.

Dropping a required Python version, implementation, operating-system tier, or architecture requires:

- a dedicated Issue;
- documented rationale and impact;
- migration notice;
- changelog entry;
- release-policy review;
- an appropriate version bump.

## 17. Release authorization

Only the project lead may authorize:

- a normal public release;
- a production package-index publication;
- correction of an unpublished private tag mistake;
- an emergency compatibility exception;
- changes to License, DCO/CLA model, build backend, or version source.

## 18. P0/P1 relationship

The project lead's merge of PR #51 accepts this policy, freezes P0, and authorizes the P1 implementation scope.

It does not authorize public package publication, production-readiness claims, or implementation outside `P1_IMPLEMENTATION_PLAN.md`.
