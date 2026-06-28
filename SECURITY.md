# Security Policy

## Reporting a vulnerability

Do not disclose an unpatched vulnerability in a public Issue, Pull Request, Discussion, commit message, test log, or chat transcript.

Preferred reporting channel:

1. Open the repository **Security** tab.
2. Choose **Report a vulnerability**.
3. Submit a private advisory with reproduction details and impact.

Before the first public release, repository maintainers must enable GitHub Private Vulnerability Reporting. If the private reporting button is unavailable, use a private contact channel listed on the maintainer's GitHub profile and provide only enough information to establish a secure follow-up channel. Do not place exploit details in a public issue.

## Information to include

Provide, where available:

- affected LingShu version or commit;
- affected Python, operating system, and deployment mode;
- vulnerability class and expected security property;
- minimal reproduction or proof of concept;
- impact and realistic attack prerequisites;
- whether exploitation crosses process, network, tenant, privilege, or trust boundaries;
- logs or Runtime Record excerpts after removing secrets and personal data;
- suggested mitigation or patch, when known;
- disclosure constraints or deadlines already agreed with another party.

Do not include live credentials, access tokens, private keys, personal data, production request bodies, or unrelated customer information.

## Maintainer response targets

These are best-effort targets, not contractual service-level guarantees:

- acknowledge a credible report within 3 business days;
- complete initial triage within 7 business days;
- agree on severity, scope, and disclosure plan as soon as evidence permits;
- provide material progress updates at least every 14 days while remediation remains open;
- publish a coordinated advisory after a fix or mitigation is available.

Complex reports, incomplete reproductions, third-party coordination, or embargo requests may require more time.

## Supported versions

Before 1.0:

| Version | Security support |
|---|---|
| Latest `0.y` minor line | Supported |
| Older `0.y` minor lines | Not supported unless explicitly announced |
| Unreleased `main` | Best effort; not a released support promise |

After 1.0, the project will support the latest minor line of the current major. When a new major is released, the previous major receives critical/high-severity fixes for a transition window announced in the release policy, normally 180 days.

A release may be declared unsupported early when the runtime platform itself is unsupported or when safe remediation cannot be delivered without a breaking change. Such decisions must be documented publicly after coordinated disclosure permits it.

## Severity and remediation

Severity considers exploitability, confidentiality, integrity, availability, auditability, cross-tenant impact, privilege boundaries, remote reachability, and required user interaction.

Possible responses include:

- a patch release;
- a new pre-1.0 minor release when a breaking security correction is unavoidable;
- a mitigation or configuration change;
- a release yanked from the package index;
- a dependency or supported-platform restriction;
- a delayed coordinated disclosure.

Security and correctness may override normal deprecation windows. Emergency exceptions must be narrowly scoped, documented in the advisory and changelog, and followed by migration guidance.

## Disclosure and credit

The project prefers coordinated disclosure. Reporter credit is included when requested and legally permissible. Anonymous reporting and no-credit requests are respected.

Maintainers may reject or close reports that contain no plausible security impact, duplicate an existing report, target unsupported versions only, or require unsafe testing against systems the reporter does not own or have permission to assess.

## Security updates

Security fixes are documented in:

- a GitHub Security Advisory;
- `CHANGELOG.md` under `Security`;
- release notes;
- migration or mitigation instructions when user action is required.

Published artifacts are never silently replaced. A flawed release is yanked or superseded by a new version.
