<!-- One module / one phase per PR. Keep PRs scoped to a requirement ID. -->

## Module / Phase
<!-- e.g. "Phase 0 — Access Control" / requirement IDs: DEP-01, USR-02 -->

- Module/Phase:
- Requirement ID(s):
- Target branch: <!-- dev1 for new work; dev2/test/prod for promotions -->

## Summary
<!-- What this PR does and why. -->

## Docs
- [ ] README / module docs added or updated for this change

## Definition of Done (per CLAUDE.md §11)
- [ ] Matches the requirement ID + acceptance criteria
- [ ] Tenant-scoped (cannot read/write another tenant's data)
- [ ] Permission checks present (role + object-level where applicable)
- [ ] Input validated server-side; output safe
- [ ] Action is audited
- [ ] Tests written, including a permission/isolation test
- [ ] `/security-review` run — no HIGH/CRITICAL findings
- [ ] No secrets, PII, or financial data in code or logs
- [ ] Any new dependency is open-source and license-checked
