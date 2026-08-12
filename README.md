# GoreeCloud Tasks

Privacy-first, self-hosted, multi-user task and project management for personal,
family, collaborative, and GoreeCloud operational work.

## Status

**v0.1 foundation development. Production deployment is not yet approved.**

The current scaffold establishes the security and identity boundary before
advanced task features are added.

## Current Foundation

- Custom Django user model created before the first application migration.
- Individual accounts and private personal task boundaries.
- Private and explicitly shared projects.
- Project Manager, Member, and Viewer roles.
- Authorization-aware task query helpers for read and edit access.
- GoreeCloud P0 through P4 priorities with lifecycle status kept separate.
- Django admin limited to account administration; private task/project content
  is not registered there.
- PostgreSQL-ready production data model with SQLite available for isolated
  local development and tests.
- File-based secret support.
- Dockerfile and development Docker Compose stack.
- Loopback-only development web-port publication and no published database port.
- Non-sensitive `/health/` endpoint.
- Automated Django checks, migration checks, and multi-user authorization tests
  in GitHub Actions.

## Technology

- Python 3.13
- Django 5.2 LTS
- PostgreSQL 17 for multi-user Docker development and planned production use
- SQLite for isolated local development and automated tests
- Gunicorn
- Docker and Docker Compose
- GitHub Actions

Dependencies and container base images are deliberately version-pinned. Image
digests are included for the current development images so recreation does not
silently select different image content.

## Local Python Development

Create and activate an isolated Python environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements.txt
```

Set development-only configuration in the current shell:

```bash
export DJANGO_SECRET_KEY='replace-with-a-development-only-secret'
export DJANGO_DEBUG='true'
```

Initialize the database and create the first local administrative account:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The default development address is `http://127.0.0.1:8000/`.

## Docker Development

Create the protected local configuration from the sanitized template:

```bash
cp .env.example .env
mkdir -p secrets
python -c "import secrets; print(secrets.token_urlsafe(64))" > secrets/django_secret_key
python -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/postgres_password
chmod 600 .env secrets/django_secret_key secrets/postgres_password
```

Validate and build the stack before starting it:

```bash
docker compose config --quiet
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose up -d web
docker compose ps
```

The development database is reachable only on the internal Compose network.
The web service is published only on host loopback by default.

Do not commit `.env` or files under `secrets/`.

## Tests

Run the local checks with:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Multi-user authorization tests are launch-blocking. The initial suite verifies
that private tasks do not cross user boundaries, shared membership is explicit,
Viewer access remains read-only, deactivated memberships remove future access,
staff/superuser status does not bypass the normal task query boundary, and
personal tasks cannot be assigned to another user.

## Repository Structure

```text
goreecloud-tasks/
├── goreecloud_tasks/   # Django project configuration
├── accounts/           # Individual user identity and preferences
├── projects/           # Project ownership, memberships, and roles
├── tasks/              # Core task model and task views
├── templates/          # Server-rendered application templates
├── static/             # CSS and future client-side assets
├── tests/              # Application and authorization tests
├── docs/               # Architecture and operating documentation
├── .github/workflows/  # Continuous integration
├── compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── manage.py
```

Additional apps such as labels, activity history, imports, integrations, and a
public application API will be introduced only when their milestone requires
them.

## License

The repository is private while the foundation is being developed. The
open-source license is intentionally **TBD** and must be selected and added
before any public release.
