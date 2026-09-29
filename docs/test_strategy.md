# Test strategy

- **API:** exercise the local HTTP server through the same network boundary a
  real client uses. A smoke health check verifies service availability before
  endpoint-specific scenarios cover success, missing resources, invalid input
  and response shape. Unsupported user methods return HTTP 405 with the allowed
  methods. Parameterized checks cover collection and individual user URLs,
  query strings, and valid or malformed request bodies. Rejected methods preserve
  existing users and the next created user ID, with JSON headers and body verified.
  User names are trimmed and email addresses are trimmed and lowercased
  before creation. Every test starts with fresh in-memory users.
- **Data:** run SQL rules against an in-memory SQLite fixture. The baseline
  records known training defects; a separate test adds a defect to show that
  the rules detect drift. Order statuses are limited to `NEW` and `PAID`;
  an unknown status is a new defect rather than part of the baseline. Payments
  must reference an existing order and have the `SUCCESS` status.
- **UI:** use Playwright with a real Chromium browser against the local page.
  It runs separately because browser installation is larger than core pytest.
- **CI:** lint and core tests run in one job; the browser has its own job on
  GitHub Actions and GitLab CI. Both publish JUnit and QA summary reports even
  if a test fails.

When adapting this lab to a real system, replace the local server with an
environment-specific base URL and avoid putting credentials in source files.
