from setuptools import find_packages, setup


install_requires = [
    "tqdm",
    "pyyaml",
    "packaging",
]

extras = {}

extras["transformers"] = [
    "transformers[dev]",
]

setup(
    name="doc-builder",
    version="0.0.1.dev0",
    author="Hugging Face, Inc.",
    author_email="sylvain@huggingface.co",
    description="Doc building utility",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    keywords="doc documentation doc-builder huggingface hugging face",
    url="https://github.com/huggingface/doc-builder",
    package_dir={"": "src"},
    packages=find_packages("src"),
    extras_require=extras,
    install_requires=install_requires,
    entry_points={"console_scripts": ["doc-buider=doc_builder.commands.doc_builder_cli:main"]},
)
