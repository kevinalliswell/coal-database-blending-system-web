#!/bin/sh
set -eu
# Run once before Gunicorn forks workers; requests never create or alter tables.
python -m flask --app wsgi initialize
exec "$@"
