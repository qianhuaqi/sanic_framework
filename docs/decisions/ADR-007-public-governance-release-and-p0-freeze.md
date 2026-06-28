# ADR-007: Public governance, compatibility, release policy, and P0 final freeze

- Status: Accepted when PR #51 is merged
- Date: 2026-06-28
- Parent architecture Issue: #25 (closed by PR #51)
- Decision Issue: #49 (closed by PR #51)
- Decision proposal: PR #50
- Final Freeze and P1 authorization: PR #51
- Effective P0 freeze commit: the merge commit of PR #51
- Detailed policies:
  - `docs/governance/RELEASE_AND_COMPATIBILITY_POLICY.md`
  - `docs/development/P1_IMPLEMENTATION_PLAN.md`
  - `docs/architecture/P0_FINAL_FREEZE.md`

## Context

LingShu completed its technical P0 decisions but could not authorize implementation without public governance, license, security reporting, compatibility rules, release controls, a first development version, an executable P1 dependency graph, and one explicit freeze event.

## Decision

### License

LingShu uses Apache License 2.0.

The repository contains:

```text
LICENSE
NOTICE
```

P1 package metadata uses SPDX identifier `Apache-2.0`. Required third-party attribution is appended to NOTICE. Changing the license requires a dedicated Issue, compatibility/legal review, and project-lead approval.

### Contributions

LingShu uses Developer Certificate of Origin 1.1.

- every commit requires `Signed-off-by`;
- `git commit -s` is the normal workflow;
- unsigned commits block merge until corrected;
- no Contributor License Agreement is required initially;
- accepted contributions are Apache-2.0 unless validly designated otherwise before submission;
- one Issue, one writer-prefixed branch, one primary writer, one isolated environment, and one PR remain mandatory;
- the project lead retains final merge authority;
- automatic merge remains prohibited.

### Code of Conduct

The repository uses a LingShu-specific policy adapted from Contributor Covenant 2.1. It applies to public and private official project spaces and includes confidential reporting, conflict-of-interest handling, proportionate enforcement, and protection against retaliation.

### Security reporting and support

GitHub Private Vulnerability Reporting is the preferred channel and must be enabled before the first public release.

- unpatched exploit details are not posted publicly;
- credible reports have a best-effort acknowledgement target of 3 business days;
- initial triage target is 7 business days;
- material progress is communicated at least every 14 days while remediation remains active;
- disclosure is coordinated;
- reporter credit and anonymity preferences are respected where lawful and practical;
- advisories, changelog entries, and migration/mitigation guidance are published when appropriate.

Before 1.0, only the latest `0.y` minor line is supported unless otherwise announced. After 1.0, the current major's latest minor is supported; after a new major, the previous major normally receives critical/high-severity fixes for 180 days.

### Versioning

LingShu follows Semantic Versioning 2.0.0 with stricter project rules for `0.x`.

First P1 development version:

```text
0.1.0.dev0
```

Git tags use `vX.Y.Z` and corresponding prerelease forms. Package metadata omits the `v` prefix. Published versions, tags, and artifacts are immutable.

### Pre-1.0 compatibility

Patch releases inside one `0.y` line remain backward compatible except for narrowly approved security or severe correctness emergencies.

A breaking public change before 1.0:

- requires a new minor release;
- is explicit in changelog and release notes;
- includes migration guidance;
- updates contract tests and public export manifests;
- avoids unrelated breakage;
- should normally be deprecated for at least one released minor where practical.

Major version zero does not permit undocumented arbitrary breakage.

### Compatibility after 1.0

- patch releases contain backward-compatible fixes;
- minor releases contain backward-compatible features and deprecations;
- major releases contain incompatible public changes.

Normal removal requires at least two released minor versions and at least 180 days of deprecation. Security, data-corruption, protocol-ambiguity, privilege-boundary, audit, or severe correctness failures may use a narrow documented exception approved by the project lead.

### Public API boundary

Public API consists only of documented/exported names and documented CLI, configuration, wire, package-metadata, and stable error-code contracts. Importable private implementation is not automatically public.

### Branch and release model

- `main` is the only long-lived integration branch;
- no long-lived `develop` branch;
- normal work uses short-lived Issue branches;
- `release/X.Y` is allowed only as a short-lived stabilization branch;
- release and security fixes merge back to `main`;
- a release PR updates version and changelog but does not publish before merge;
- an annotated tag triggers protected CI artifact construction;
- authoritative artifacts are built from the tag by CI;
- tag, project version, wheel/sdist metadata, changelog, and release notes must agree;
- defective releases are yanked or superseded, never overwritten.

### Publication credentials and provenance

Before a public package-index release:

- use short-lived identity-based trusted publishing where supported;
- do not store long-lived production package-index credentials in CI;
- retain artifact hashes and verifiable provenance/attestation;
- separate test/staging publication from production publication;
- require explicit project-lead authorization for production publication.

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

User-visible PRs update `Unreleased` unless explicitly exempted. Released sections are dated and immutable in substance. Security entries may remain embargoed until coordinated disclosure.

### P1 scope

P1 is the single-Worker minimum vertical slice defined in `docs/development/P1_IMPLEMENTATION_PLAN.md`.

P1 includes:

- package, tooling, CI, and governance enforcement;
- core time, identifiers, errors, and static configuration;
- runtime Scope, Deadline, cancellation, tasks, and admission;
- HTTP Request, Response, body, Router, and Middleware foundations;
- Application Kernel, Revision, freeze, and lifecycle;
- minimum Runtime Record;
- native single-Worker HTTP/1.1 Server;
- CLI `version`, `check`, and `run --workers 1`;
- wheel/sdist and clean-install verification.

P1 excludes:

- multi-Worker Supervisor implementation;
- listener transfer between processes;
- development reload;
- production configuration reload/rollout;
- advanced streaming, multipart, uploads, and compression;
- official integrations/extensions;
- HTTP/2, HTTP/3, WebSocket, ASGI, and WSGI;
- public PyPI production release.

### P1 dependency graph

P1 uses P1-00 through P1-10 with provider-first integration, exact write scopes, limited non-overlapping parallel waves, and one PR per Issue.

The exact executable GitHub Issues are created only after PR #51 merges. P1-00 is created first and is based on the PR #51 merge commit.

### P0 final freeze

PR #50 created the Freeze Candidate. It did not authorize implementation.

The project lead's merge of PR #51:

1. accepts ADR-007;
2. freezes the Blueprint;
3. establishes the PR #51 merge commit as the final P0 commit;
4. closes Issue #49 and parent Issue #25 through PR close directives;
5. authorizes P1;
6. permits P1-00 to create `pyproject.toml`, the initial `lingshu/` and `tests/` skeletons, tooling configuration, and CI workflows within its declared scope;
7. permits later P1 Issues only after their provider dependencies merge.

No approval, comment, branch commit, or PR #50 merge is a substitute for the PR #51 merge authorization.

## Final verification requirements

PR #51 verifies:

- Apache License 2.0 and NOTICE are present;
- DCO 1.1 is present and CONTRIBUTING requires sign-off;
- private security reporting and supported-version policy are documented;
- Code of Conduct includes confidential reporting and conflict handling;
- changelog, SemVer, deprecation, release, and rollback rules agree;
- ADR-001 through ADR-007 and the single Blueprint have no active contradiction;
- the P1 plan respects package, ownership, dependency, and scope boundaries;
- no production package, test skeleton, `pyproject.toml`, implementation workflow, runtime dependency, or executable P1 Issue existed before Final Freeze.

## Rejected alternatives

- missing or placeholder license metadata;
- initial proprietary licensing;
- CLA-only contribution requirements;
- unsigned contributions without DCO;
- public vulnerability Issues as the primary reporting channel;
- arbitrary breaking patch releases during `0.x`;
- rewriting published tags or artifacts;
- long-lived `develop`;
- developer-workstation artifacts as authoritative releases;
- long-lived production package-index credentials in CI;
- auto-merge;
- automatic P1 start after PR #50;
- broad P1 implementation before the single-Worker vertical slice.

## Intentionally deferred

- first public release date and package-index creation timing;
- manual signature scheme beyond provenance/attestation;
- trademark policy;
- paid/enterprise support;
- post-1.0 LTS branches;
- governance bodies beyond project lead and contributors;
- all implementation work assigned to P1 and later phases.
