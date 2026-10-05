# Branch protection for `main`

`main` is the trunk (team Way of Working). Every change reaches it through a pull request
that is squash-merged, named by its Bolt slug, and only when CI is green (BR8.6, AC1.3.2).

This is a repository setting, so it is switched on once by a repository admin. It is not
something CI can apply to itself.

## Settings (GitHub → Settings → Branches → Add branch ruleset, target `main`)

| Setting | Value |
|---|---|
| Restrict deletions | On |
| Block force pushes | On |
| Require a pull request before merging | On |
| Required approvals | **0** for now (plan decision D9: a sole maintainer must be able to merge). Raise it to 1 when a second maintainer joins |
| Require status checks to pass | On, with "Require branches to be up to date before merging" |
| Required checks | `backend`, `frontend`, `e2e`, `security` (the job names in `.github/workflows/ci.yml`) |
| Allowed merge methods | Squash only |
| Require linear history | On |

## With the GitHub CLI

```bash
gh api -X PUT repos/Shrutipatel9/AI-DLC-Demo/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=backend" \
  -f "required_status_checks[contexts][]=frontend" \
  -f "required_status_checks[contexts][]=e2e" \
  -f "required_status_checks[contexts][]=security" \
  -F "enforce_admins=true" \
  -F "required_pull_request_reviews[required_approving_review_count]=0" \
  -F "restrictions=null" \
  -F "required_linear_history=true" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false"
gh api -X PATCH repos/Shrutipatel9/AI-DLC-Demo \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false
```

Run this after the first push, once the four checks have reported at least once (GitHub only
offers checks it has seen).

## Also enable

- **Dependabot alerts and security updates** (Settings → Code security). Version updates are
  configured in `.github/dependabot.yml`.
- **Secret scanning and push protection**, if available for the repository.
