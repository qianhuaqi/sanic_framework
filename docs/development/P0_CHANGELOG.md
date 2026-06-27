# P0 Architecture Changelog

## Blueprint v0.6

Commits on `research/lingshu-framework-blueprint`:

- `6093b295a27f8e8436fc85d9a6814ff06a889466` — complete v0.6 Blueprint with package layout, source tree, code documentation standard, process model, startup/shutdown flow and request execution chain;
- `1c2b03fdeb871c233c366336173af5ef837ef801` — remove the v0.5 addendum after merging it into the single authoritative Blueprint;
- `57a25353d939d3203e13c291d5cd26dcb5007ddd` — add ADR-006 for independent Core/HTTP/Record/Server structure;
- `94a970f36bb5892e15a47280b539a540e3395331` — define P1 implementation readiness gate;
- `8469db3ea2bb4bb4c76c9c392dd9ac54114cf9ab` — add P0 final review checklist.

The only authoritative overall design is now:

```text
docs/architecture/LINGSHU_FRAMEWORK_BLUEPRINT.md
```

No production implementation may start before the user confirms and freezes P0.
