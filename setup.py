from setuptools import find_packages, setup

install_requires = ["tqdm", "pyyaml", "packaging", "nbformat"]

extras = {}

extras["transformers"] = ["transformers[dev]"]
extras["testing"] = ["pytest", "pytest-xdist", "torch", "transformers"]
extras["quality"] = ["black~=22.0", "isort>=5.5.4", "flake8>=3.8.3"]

extras["all"] = extras["testing"] + extras["quality"]
extras["dev"] = extras["all"]


setup(
    name="hf-doc-utils",
    version="0.0.1.dev0",
    author="Hugging Face, Inc.",
    author_email="sylvain@huggingface.co",
    description="Doc building utility",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    keywords="doc documentation doc-builder huggingface hugging face",
    url="https://github.com/huggingface/hf-doc-utils",
    package_dir={"": "src"},
    packages=find_packages("src"),
    extras_require=extras,
    install_requires=install_requires,
    entry_points={"console_scripts": ["hf-doc-utils=hf_doc_utils.commands.hf_doc_utils_cli:main"]},
)
