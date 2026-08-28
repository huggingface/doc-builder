# Release checklist

1. Checkout the release branch (for a patch the current release branch, for a new minor version, create one):
   ```bash
   git checkout -b vXX.xx-release
   ```
   The `-b` is only necessary for creation (so remove it when doing a patch).
2. Change the version in `src/doc_builder/__init__.py` and `pyproject.toml` to the proper value.
3. Commit these changes with the message: `"Release: v<VERSION>"`.
4. Add a tag in git to mark the release:
   ```bash
   git tag v<VERSION> -m 'Adds tag v<VERSION> for pypi'
   ```
   Push the tag and release commit to git:
   ```bash
   git push --tags origin vXX.xx-release
   ```
5. Build the source distribution and the wheel in the top-level directory:
   ```bash
   rm -rf dist
   uv build
   ```
6. Upload the package to the pypi test server first:
   ```bash
   twine upload dist/* -r testpypi
   ```
7. Check that you can install it in a virtualenv by running:
   ```bash
   pip install hf-doc-builder
   pip uninstall hf-doc-builder
   pip install -i https://test.pypi.org/simple/ hf-doc-builder
   ```
   It's recommended to check that there are no issues building the docs, so try running a command like `doc-builder`.
8. Upload the final version to actual pypi:
   ```bash
   twine upload dist/* -r pypi
   ```
9. Add release notes to the tag in github once everything is looking hunky-dory.
10. Go back to the main branch and update the version in `src/doc_builder/__init__.py` and `pyproject.toml` to the new
    version ".dev" and push to main.
