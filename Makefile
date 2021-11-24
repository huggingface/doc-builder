.PHONY: test

# Run tests for doc-builder
test:
	python -m pytest -n 1 --dist=loadfile -s -v ./tests/

doc:
	python src/build.py transformers ../transformers/docs/source/