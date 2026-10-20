# Releasing

How this SDK is set up for publishing and how a release is cut. The workflow
is the same shape across the Onetime Secret SDKs and tooling (`rots`,
`onetime-ruby`): push a `vX.Y.Z` tag, CI verifies the tag matches the package
version, builds, publishes through the registry's trusted-publishing (OIDC)
flow, and creates the GitHub Release. No registry token is stored anywhere.

## Names

| What | Value |
|---|---|
| Repository | `onetimesecret/onetimesecret-py` |
| Distribution (PyPI) | `onetime-secret` |
| Import name | `onetimesecret` |
| Version source | `src/onetimesecret/_version.py` (`__version__`) |
| Workflow | `.github/workflows/release.yml` |
| GitHub environment | `pypi` |

Repository, distribution and import names do not need to match; the Ruby SDK
follows the same pattern (`onetime-ruby` / `onetimesecret` / `Onetime`).

`onetimesecret` on PyPI is held by an unrelated third-party package. If it is
ever transferred to the project under
[PEP 541](https://peps.python.org/pep-0541/), renaming is a one-line change to
`[project].name` in `pyproject.toml`, the `url:` in `release.yml`, and a
release note.

## Initial setup (once per repository)

Do these before the first tag. Steps 1 and 2 can be done in either order; the
first publish will fail until both exist.

### 1. PyPI: pending trusted publisher

The project does not exist on PyPI yet, so register a *pending* publisher,
which reserves the name and binds it to this repository's workflow.

1. Sign in to PyPI with an account that should own the project (use the
   shared organisation account, not a personal one, so ownership survives
   staff changes).
2. Open **Your account → Publishing → Add a new pending publisher** and
   enter:

   | Field | Value |
   |---|---|
   | PyPI project name | `onetime-secret` |
   | Owner | `onetimesecret` |
   | Repository name | `onetimesecret-py` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

   Every field must match exactly; PyPI compares them against the OIDC
   token's claims.

After the first successful publish, PyPI converts the pending publisher into
a normal trusted publisher on the project and makes the registering account
an owner. Add the other maintainers as owners then.

For a project that already exists on PyPI, add the publisher under the
project's **Manage → Publishing** page instead; the fields are the same.

### 2. GitHub: `pypi` environment

1. **Settings → Environments → New environment**, named `pypi`.
2. Under *Deployment branches and tags*, choose **Selected branches and
   tags** and add the tag pattern `v*`. A workflow run from anything else
   cannot use the environment, so cannot mint a publishing token.
3. Optionally add **Required reviewers**. The `publish` job then pauses for
   approval after `build` succeeds, which gives a last look at the built
   distributions before anything is uploaded.

No secrets are added to the environment. The `publish` job's only
credential is the short-lived OIDC token GitHub mints for it
(`id-token: write`), which PyPI verifies against the publisher record above.

### 3. GitHub: repository settings

- **Settings → Actions → General → Workflow permissions**: *Read repository
  contents and packages permissions* is sufficient. Each job in
  `release.yml` requests what it needs (`id-token: write` to publish,
  `contents: write` to create the release).
- Protect the `v*` tag pattern under **Settings → Tags** (or a ruleset) so
  that only maintainers can push release tags.
- Enable Dependabot alerts and security updates. `.github/dependabot.yml`
  already keeps the pinned action SHAs and the `uv.lock` dev dependencies
  current.

### 4. Verify

Push a tag for the current `__version__` only when you intend to release.
To rehearse the pipeline without publishing, open a pull request: the CI
`build` job runs `uv build` and `twine check` and smoke-installs the wheel
in a clean environment, which is everything the release's `build` job does
short of uploading.

## Cutting a release

1. Confirm `main` is green.
2. In `CHANGELOG.md`, move the `[Unreleased]` entries under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading and add the comparison link at the
   bottom of the file.
3. Set `__version__ = "X.Y.Z"` in `src/onetimesecret/_version.py`.
4. Commit as `Release vX.Y.Z`, open a pull request, merge to `main`.
5. Tag the merge commit and push the tag:

   ```sh
   git switch main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

6. Watch **Actions → Release**. The run:
   - fails fast if the tag does not equal `__version__`;
   - runs ruff, mypy and pytest, then builds and checks the sdist and wheel;
   - publishes to PyPI (pausing for approval if reviewers are configured);
   - creates the GitHub Release `vX.Y.Z` with generated notes and the
     distributions attached.
7. Confirm the new version is visible at
   <https://pypi.org/project/onetime-secret/> and installs:

   ```sh
   uv run --isolated --with onetime-secret==X.Y.Z python -c "import onetimesecret; print(onetimesecret.__version__)"
   ```

8. Edit the GitHub Release notes if the generated ones need context, and
   paste the changelog section in.

### If the run fails

- **Tag/version mismatch**: delete the tag (`git push --delete origin
  vX.Y.Z`), fix the version, re-tag. Nothing was uploaded.
- **Publish rejected by PyPI** (`invalid-publisher`): the publisher record
  does not match the workflow's claims. Re-check the five fields in step 1,
  especially the environment name. Nothing was uploaded; re-run the job.
- **Publish succeeded but a later job failed**: PyPI releases are immutable,
  so the version is taken. Fix forward with a patch release. The
  `github-release` job is idempotent and can be re-run on its own.

## Versioning

Semantic Versioning. While the major version is `0`, minor releases may
contain breaking changes; they are called out in the changelog under
**Changed** or **Removed** with a migration note.

## Adapting this for another SDK

Copy `release.yml` and this document, then change: the version-extraction
command, the distribution name and registry URL, and the registry publishing
action. Keep the three-job split (build → publish → github-release), the
tag/version check, the environment gate, and the SHA-pinned actions.
