# GoreeCloud Tasks

Privacy-first, self-hosted, multi-user task and project management for personal,
family, collaborative, and GoreeCloud operational work.

## Status

**v0.1 development. Production deployment is not yet approved.**

The current implementation establishes the multi-user security boundary and the
first usable task workflows. Production publication remains blocked on the
broader v0.1 acceptance requirements, including backup and restoration testing.

## Implemented Foundation

- Custom Django user model created before the first application migration.
- Individual accounts and private personal task boundaries.
- Private and explicitly shared projects.
- Project Manager, Member, and Viewer roles.
- Authorization-aware task query helpers for read and edit access.
- Server-side mutation checks that prevent ordinary users from editing work they
  are not authorized to change.
- GoreeCloud P0 through P4 priorities with lifecycle status kept separate.
- Task creation through Quick Add and the full task editor.
- Task editing, completion, reopening, and deletion.
- Inbox, Today, and Upcoming views.
- Project-aware Quick Add limited to projects the current user may edit.
- Read-only presentation for tasks visible through Viewer membership.
- Django admin limited to account administration; private task/project content
  is not registered there.
- PostgreSQL-ready application configuration with SQLite for isolated tests.
- File-based secret support.
- Dockerfile and Docker Compose development stack.
- Loopback-only development web-port publication and no published database port.
- Non-sensitive `/health/` endpoint.
- GitHub Actions checks for Django configuration, migration drift, application
  tests, Docker image build, PostgreSQL-backed migrations, Compose startup, and
  live health verification.

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

Validate, build, migrate, and start the stack:

```bash
docker compose config --quiet
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d web
docker compose ps
curl --fail http://127.0.0.1:8000/health/
```

The development database is reachable only on the internal Compose network.
The web service is published only on host loopback by default.

Do not commit `.env` or files under `secrets/`.

## Task Workflows

After signing in, the application provides:

- **Inbox** for active private personal tasks.
- **Today** for active accessible tasks due on the current GoreeCloud local date.
- **Upcoming** for active accessible tasks due after the current local date.
- **Quick Add** for low-friction capture into Inbox or an editable project.
- **Full editor** for title, description, project, assignee, priority, status, and
  optional due date/time.
- **Completion controls** for completing and reopening editable tasks.

Shared-project Viewer membership remains read-only. Manager and Member roles may
modify shared project work according to the project authorization boundary.

## Tests

Run the local checks with:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Multi-user authorization tests are launch-blocking. The suite verifies private
user boundaries, explicit shared membership, Viewer read-only behavior,
deactivated memberships, administrator separation, assignment constraints,
Quick Add authorization, task mutation authorization, and Today/Upcoming
visibility behavior.

GitHub Actions additionally builds and starts the Docker Compose development
stack with PostgreSQL, applies migrations, and verifies the live health endpoint.

## Repository Structure

```text
goreecloud-tasks/
├── goreecloud_tasks/   # Django project configuration
├── accounts/           # Individual user identity and preferences
├── projects/           # Project ownership, memberships, and roles
├── tasks/              # Core task models, forms, views, and authorization
├── templates/          # Server-rendered application templates
├── static/             # CSS and future client-side assets
├── tests/              # Functional and authorization tests
├── docs/               # Architecture and operating documentation
├── .github/workflows/  # Continuous integration
├── compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── manage.py
```

Additional apps and capabilities such as labels, subtasks, activity history,
comments, imports, integrations, reminders, and the public application API will
be introduced only when their milestone requires them.

## Production Boundary

This repository does not yet authorize production publication. Production use
still requires the project specification's security, authorization, persistent
storage, backup, restore, monitoring, reverse-proxy, upgrade, rollback, and
multi-user acceptance requirements to be completed and documented.

## License

The repository is private while the application is being developed. The
open-source license is intentionally **TBD** and must be selected and added
before any public release.
