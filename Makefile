.PHONY: install test demo eval audit wheel
install:
	python -m pip install -e '.[dev,mcp]'
test:
	python -m pytest -q
demo:
	fabric demo
eval:
	fabric-evaluate --fixture benchmarks/fixtures/coding-agent-mini.json --k 3
audit:
	python -m pip install pip-audit && pip-audit
wheel:
	python -m pip wheel --no-deps --wheel-dir dist .
