none:

docker-build:
	@docker build -t hasty-paste .

py-venv:
	@python -m venv .venv

py-install:
	@python -m pip install .

run:
	hypercorn 'asgi:paste_bin.main:create_app()' --bind 0.0.0.0:8000 --workers 1
