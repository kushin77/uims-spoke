# PR Submission Checklist

Before opening the PR ensure:

- [ ] Code compiles and tests pass locally: `PYTHONPATH=. pytest`
- [ ] `terraform fmt -check` passes for any `.tf` changes
- [ ] No secrets in commits: `gitleaks detect --source=.`
- [ ] Commit messages reference issues: `Closes #123`
- [ ] Branch created from `main` and rebased as needed

Reviewer checklist:

- [ ] CI green
- [ ] Changes scoped and atomic (1-5 files per commit preferred)
- [ ] Security review for IAM/keys
- [ ] Documentation updated
