# If the VIRTUAL_ENV is specified, we can assume we're in a poetry shell, otherwise
# we need to execute "poetry run"
ifdef VIRTUAL_ENV
POETRY_RUN=
else
POETRY_RUN=poetry run
endif

lint:
	# Run lint.
	$(POETRY_RUN) pylint ./*.py;