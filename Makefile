.PHONY: quality style test

check_dirs := tests src

# Make sure to install timm, pytest, transformers
test:
	python -m pytest -n 1 --dist=loadfile -s -v ./tests/


doc:
	doc-builder build transformers ../transformers/docs/source/

quality:
	black --check $(check_dirs)
	isort --check-only $(check_dirs)
	flake8 $(check_dirs)

style:
	black $(check_dirs)
	isort $(check_dirs)
