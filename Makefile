.PHONY: setup test lint sample cost validate deploy send destroy

setup:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	terraform -chdir=terraform fmt -check -recursive

sample:
	mkdir -p data
	uv run python -m shopgen --sessions 1000 --out data/sample.ndjson
	@wc -l data/sample.ndjson

cost:
	uv run python -m costmodel

validate:
	terraform -chdir=terraform init -backend=false -input=false
	terraform -chdir=terraform validate

deploy:
	terraform -chdir=terraform init -input=false
	terraform -chdir=terraform apply

send:
	uv run python -m shopgen --sessions 1000 --post $(URL) --token $(TOKEN)

destroy:
	terraform -chdir=terraform destroy
