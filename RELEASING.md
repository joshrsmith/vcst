# Releasing

Versions come from git tags, so there is no version to edit in a file. A tag `v0.1.0` makes version 0.1.0, and a
commit after it is a development version of the next one, e.g. 0.1.1.dev3.

## Making a release

1. Make sure the checks of `main` have passed. The release runs them again, and stops if they fail.
2. Tag the commit of `main` to release, and push the tag:

   ```sh
   git tag -a v0.1.0 -m "VCST 0.1.0"
   git push origin v0.1.0
   ```

   Use `v0.2.0rc1` (or `a1`, `b1`) for a prerelease. Tags that are not like `v1.2.3` or `v1.2.3rc1`, or that are
   not on a commit of `main`, stop the release without publishing anything.
3. The Release workflow checks the tag, builds the package, runs the tests, and creates the GitHub release for the tag
   with the built files and generated release notes. A prerelease is marked as one.

A release can't be undone by moving the tag. If something is wrong, delete the GitHub release and the tag, fix it,
and tag again, or make a new version.

## Version numbers

`MAJOR.MINOR.PATCH`. While MAJOR is 0, a change that breaks users raises MINOR. Fixes that don't raise PATCH.

## What runs when

- `build.yml`, on every pull request and push to `main`: builds the package, checks its metadata, and installs the
  wheel in a clean environment.
- `release.yml`, on a pushed tag: described above.
