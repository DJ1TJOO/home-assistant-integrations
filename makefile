.PHONY: format lint type

format:
	python -m isort custom_components
	python -m black custom_components

lint:
	python -m pylint custom_components

type:
	python -m mypy custom_components
