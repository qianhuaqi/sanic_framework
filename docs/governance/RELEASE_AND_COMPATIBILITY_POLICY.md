# LingShu Release and Compatibility Policy

- Status: Proposed for P0-D7
- Parent architecture Issue: #25
- Decision Issue: #49
- Related ADR: `docs/decisions/ADR-007-public-governance-release-and-p0-freeze.md`

## 1. Version model

LingShu follows Semantic Versioning 2.0.0:

```text
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
```

Git tags use:

```text
vMAJOR.MINOR.PATCH
vMAJOR.MINOR.PATCH-prerelease
```

The version stored in package metadata does not include the `v` prefix.

A released version and its artifacts are immutable. Any correction requires a new version.

## 2. First development version

The first P1 package skeleton uses:

```text
0.1.0.dev0
```

This is a development version, not a public stable release. Public release candidates may use:

```text
0.1.0a1
0.1.0b1
0.1.0rc1
```

The first normal public release is expected to be `0.1.0` only after its declared acceptance gate passes.

## 3. Public API definition

Public API consists only of:

- names explicitly exported by documented public modules;
- behavior explicitly promised in user documentation;
- CLI commands/options documented as public;
- stable error codes and wire formats documented as public;
- package metadata and configuration keys documented as public.

Importable implementation details are not automatically public.

The root public facade is controlled through explicit export manifests. Deep modules are private unless documentation promotes them.

## 4. Pre-1.0 compatibility

Major version zero permits rapid development, but LingShu applies stricter project rules:

### Patch releases: `0.Y.Z`

Patch releases must be backward compatible within the same minor line except for a narrowly scoped security or correctness emergency.

Allowed patch changes include:

- bug fixes;
- performance improvements that preserve observable contracts;
- documentation and diagnostics corrections;
- new private implementation;
- security fixes that do not require public breakage.

A patch release must not silently remove or change a documented public API.

### Minor releases: `0.Y.0`

A pre-1.0 minor release may contain breaking public changes, but every breaking change must:

- be called out in the changelog and release notes;
- include migration guidance;
- explain why compatibility could not be preserved;
- update contract tests and public export manifests;
- avoid unrelated breakage.

Where practical, removal is preceded by at least one released minor that marks the API deprecated.

## 5. Version 1.0 and later

After `1.0.0`:

- PATCH contains backward-compatible fixes;
- MINOR contains backward-compatible features and deprecations;
- MAJOR contains incompatible public changes.

A public API normally remains deprecated for at least:

```text
two released minor versions
AND
180 days
```

Removal occurs in a new major version unless a security/correctness exception applies.

## 6. Deprecation contract

A deprecation must provide:

- the deprecated symbol/behavior;
- the replacement or migration path;
- the release where deprecation begins;
- the earliest eligible removal release/time;
- a user-visible warning when runtime warning is appropriate;
- documentation and changelog entries;
- tests that preserve the deprecated behavior during the window.

Warnings must be actionable, bounded, and not emit secrets or high-cardinality data.

## 7. Emergency compatibility exceptions

Security, data corruption, protocol ambiguity, privilege-boundary failure, audit failure, or severe correctness defects may require immediate incompatible action.

An emergency exception must:

- be the narrowest safe change;
- be approved by the project lead;
- include a security advisory or incident explanation when disclosure permits;
- document affected versions and migration/mitigation;
- use an appropriate version bump;
- never rewrite existing artifacts.

## 8. Branch model

Long-lived branches:

```text
main
```

Rules:

- `main` is the only long-lived development/integration branch;
- no long-lived `develop` branch;
- normal work uses short-lived Issue branches;
- release stabilization may use short-lived `release/X.Y` only when necessary;
- security/hotfix branches are short-lived and merge back to `main`;
- final merge authority belongs to the project lead;
- no automatic merge.

## 9. Release preparation

A release Pull Request must:

1. select the version from the accepted change set;
2. update `[project].version` as the single version source;
3. move relevant `Unreleased` entries into a dated release section;
4. update support/security tables when required;
5. include migration notes for incompatible changes;
6. pass the full release matrix;
7. build wheel and sdist from a clean checkout;
8. inspect metadata, license, NOTICE, and artifact inventory;
9. install and test artifacts outside the checkout;
10. verify the tag/version/changelog relationship.

The release PR does not publish artifacts before merge.

## 10. Tagging and artifact construction

After the release PR merges:

```text
main release commit
→ annotated tag vX.Y.Z
→ protected CI build from tag
→ test/inspect artifacts
→ provenance/attestation
→ publish release notes and artifacts
→ publish to package index when authorized
```

Artifacts must be produced by CI from the tag, not uploaded from a developer workstation as the authoritative release.

The tag, project version, wheel metadata, sdist metadata, GitHub release, and changelog section must agree.

## 11. Package-index publication

Before the first public package-index release, the project must configure short-lived identity-based trusted publishing and verifiable build provenance/attestation.

CI must not store a long-lived package-index password or API token when trusted short-lived credentials are available.

Test/staging publication must be separated from production publication.

## 12. Signing and provenance

The release pipeline must preserve:

- source commit and tag identity;
- workflow identity;
- artifact hashes;
- build environment/tool versions;
- test results;
- provenance or attestation supported by the chosen release platform.

Manual signing requirements may be added later, but absence of a manual signature must not be confused with absence of provenance.

## 13. Failed release and rollback

Published artifacts are never overwritten or silently replaced.

When a release is defective:

- stop promotion/deployment where possible;
- publish a new corrected version;
- yank the defective package-index release when appropriate without deleting history;
- mark the affected release in release notes/security advisory;
- provide mitigation and upgrade guidance;
- preserve evidence and artifact hashes;
- merge all fixes back to `main`.

Git tag deletion or retargeting after public publication is prohibited except for an unreleased private mistake approved by the project lead and fully documented.

## 14. Changelog policy

`CHANGELOG.md` records notable user-visible changes.

Required categories:

```text
Added
Changed
Deprecated
Removed
Fixed
Security
```

Rules:

- every user-visible PR updates `Unreleased` unless explicitly exempted;
- internal refactors without observable effect may omit entries;
- security entries may remain embargoed until coordinated disclosure;
- breaking changes include migration guidance;
- released sections are dated;
- release notes may be richer but must not contradict the changelog.

## 15. Security support policy

Before 1.0, only the latest `0.y` minor line is supported unless otherwise announced.

After 1.0, the latest minor of the current major is supported. After a new major release, the previous major normally receives critical/high-severity fixes for 180 days.

Exact supported versions are maintained in `SECURITY.md` and release notes.

## 16. Dependency and platform changes

A new mandatory runtime dependency requires a dedicated dependency review/ADR.

Dropping a required Python version, implementation, operating system tier, or architecture requires:

- a dedicated Issue;
- documented rationale and impact;
- migration notice;
- changelog entry;
- release-policy review;
- a version bump appropriate to the compatibility impact.

## 17. Release authorization

Only the project lead may authorize:

- a normal public release;
- a package-index production publication;
- retagging an unpublished private mistake;
- an emergency compatibility exception;
- changing the License, DCO/CLA model, build backend, or version source.

## 18. P0 freeze relationship

This policy becomes implementation authority only after ADR-007 is accepted and the dedicated Final Freeze PR is merged.

The P0-D7 decision PR itself creates a Freeze Candidate. It does not authorize production code.
