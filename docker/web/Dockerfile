FROM python:3.12-alpine
# Ensure container is ready
RUN apk update
RUN apk add bash

WORKDIR /code
RUN pip install poetry

## Program install steps
COPY ./pyproject.toml /code/pyproject.toml
COPY ./poetry.lock /code/poetry.lock

RUN poetry install

COPY . /code

RUN chmod +x /code/docker/web/entrypoint.sh
ENTRYPOINT ["/code/docker/web/entrypoint.sh"]
