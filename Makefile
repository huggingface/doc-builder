.PHONY: quality style test

check_dirs := tests src

# Make sure to install timm, pytest, transformers
test:
	python -m pytest -n 1 --dist=loadfile -s -v ./tests/


doc:
	doc-builder build transformers ../transformers/docs/source/

quality:
	ruff check $(check_dirs) setup.py
	ruff format --check $(check_dirs) setup.py
	flake8 $(check_dirs)

style:
	ruff check $(check_dirs) setup.py --fix
	ruff format $(check_dirs) setup.py
