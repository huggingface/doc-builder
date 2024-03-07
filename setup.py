# Doc-builder package setup.
# The line above is checked by some of the utilities in this repo, do not change it.

from setuptools import find_packages, setup

install_requires = ["black", "GitPython", "tqdm", "pyyaml", "packaging", "nbformat", "huggingface_hub"]

extras = {}

extras["transformers"] = ["transformers[dev]"]
extras["testing"] = ["pytest", "pytest-xdist", "torch", "transformers", "tokenizers", "timm", "google-api-python-client", "requests"]
extras["quality"] = ["black~=22.0", "isort>=5.5.4", "flake8>=3.8.3"]

extras["all"] = extras["testing"] + extras["quality"]
extras["dev"] = extras["all"]

# Should only be utilized by core-devs for release
extras["release"] = ["twine"]


setup(
    name="hf-doc-builder",
    version="0.5.0",
    author="Hugging Face, Inc.",
    license="Apache",
    author_email="docs@huggingface.co",
    description="Doc building utility",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    keywords="doc documentation doc-builder huggingface hugging face",
    url="https://github.com/huggingface/doc-builder",
    package_dir={"": "src"},
    packages=find_packages("src"),
    extras_require=extras,
    install_requires=install_requires,
    entry_points={"console_scripts": ["doc-builder=doc_builder.commands.doc_builder_cli:main"]},
)

# Release checklist
# 1. Checkout the release branch (for a patch the current release branch, for a new minor version, create one):
#      git checkout -b vXX.xx-release
#    The -b is only necessary for creation (so remove it when doing a patch)
# 2. Change the version in __init__.py and setup.py to the proper value.
# 3. Commit these changes with the message: "Release: v<VERSION>"
# 4. Add a tag in git to mark the release:
#      git tag v<VERSION> -m 'Adds tag v<VERSION> for pypi'
#    Push the tag and release commit to git: git push --tags origin vXX.xx-release
# 5. Run the following commands in the top-level directory:
#      rm -rf dist
#      rm -rf build
#      python setup.py bdist_wheel
#      python setup.py sdist
# 6. Upload the package to the pypi test server first:
#      twine upload dist/* -r testpypi
# 7. Check that you can install it in a virtualenv by running:
#      pip install hf-doc-builder
#      pip uninstall hf-doc-builder
#      pip install -i https://testpypi.python.org/pypi hf-doc-builder
#      It's recommended to check that there are no issues building the docs, 
#      so try running a command like `doc-builder`
# 8. Upload the final version to actual pypi:
#      twine upload dist/* -r pypi
# 9. Add release notes to the tag in github once everything is looking hunky-dory.
# 10. Go back to the main branch and update the version in __init__.py, setup.py to the new version ".dev" and push to
#     main.