# Linux Update Test Platform Scope Design

## Problem

`tests/test_linux_update_integration.py` is discovered on every operating
system even though it exercises Linux process and filesystem behavior. On
Windows, POSIX executable bits are unavailable and `/bin/sh` does not exist,
so 11 tests fail before reaching the behavior they intend to verify.

The release workflows already run this module only on Linux. Other tests in
the repository use `unittest.skipUnless` for the same platform boundary.

## Decision

Import `sys` in the test module and apply a Linux-only `unittest.skipUnless`
guard to both `LinuxHelperContractTests` and `LinuxHelperIntegrationTests`.
The guard will use `sys.platform.startswith("linux")` and explain that the
tests require Linux process and filesystem semantics.

Production updater code and CI workflow selections will remain unchanged.
All 13 tests will continue to execute on Linux and will be reported as skipped
when a cross-platform discovery command runs elsewhere.

## Alternatives Considered

- Split the two source-string assertions into an unguarded class. This retains
  two cross-platform assertions but adds structure for negligible coverage.
- Inject shell, process, executable-mode, and `/proc` behavior into production.
  This cannot make the real integration tests Windows-native and would add
  abstractions solely for tests.

## Verification

- Capture the current Windows failure as the pre-change signal.
- Re-run the module on Windows and require all 13 tests to be skipped cleanly.
- Run the full Windows discovery suite.
- Preserve the release workflow's direct Linux execution of this module.
