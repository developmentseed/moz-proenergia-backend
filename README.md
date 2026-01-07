# moz-proenergia-backend

[![Built with](https://img.shields.io/badge/Built_with-Cookiecutter_Django_Rest-F7B633.svg)](https://github.com/agconti/cookiecutter-django-rest)

Mozambique Proenergia backend.

# Prerequisites

- [Docker](https://docs.docker.com/docker-for-mac/install/)  

# Local Development

Start the dev server for local development:
```bash
docker-compose up
```

Run a command inside the docker container:

```bash
docker-compose run --rm web [command]
```


## Running without using Docker

- Create a PostgreSQL database named `proenergia`, and another one named `proenergia_test`
- Set the environment variables:

```
  export DJANGO_DB_URL="postgis://user:password@localhost:5432/proenergia"
  export DJANGO_SECRET_KEY="anyTextIsS3cr3t"
```

- Install the python dependencies with `pip install -r requirements.txt`
- To run the server, use `./manage.py runserver`
- You can create a super user with `./manage.py createsuperuser`

GeoDjango may require some additional libraries to be installed in your system, check the [documentation](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/#installation) or a Docker file in this repository.

To run the tests, use:

```
DJANGO_DB_URL="postgis://user:password@localhost:5432/proenergia_test" ./manage.py test --settings=proenergia.config.local
```
