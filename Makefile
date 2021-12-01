.PHONY: test

# Run tests for doc-builder
test:
	python -m pytest -n 1 --dist=loadfile -s -v ./tests/

doc:
	doc-builder build transformers ../transformers/docs/source/