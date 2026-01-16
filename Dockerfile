FROM python:3.13-slim-trixie
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq -y \
    && apt-get install -y binutils libproj-dev python3-gdal gdal-bin tippecanoe libgeos-dev libyaml-dev postgresql-client libpq-dev python3 python3-dev python3-pip \
    && apt-get clean
COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . /app
RUN useradd django
RUN chown -R django:django /app
WORKDIR /app

EXPOSE 8000
# Run the production server
CMD gunicorn --bind 0.0.0.0:$PORT --access-logfile - proenergia.wsgi:application
