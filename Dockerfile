FROM astral/uv:0.11@sha256:c4f5de312ee66d46810635ffc5df34a1973ba753e7241ce3a08ef979ddd7bea5 AS uv
FROM python:3.14-alpine@sha256:faee120f7885a06fcc9677922331391fa690d911c020abb9e8025ff3d908e510 AS base

FROM base AS builder

COPY --from=uv /uv /uvx /usr/local/bin/

RUN apk add --no-cache --update \
    # for uv-dynamic-versioning
    git

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
ADD ./pyproject.toml ./uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN rm -rf .git

FROM base

RUN apk add --no-cache --update \
    tini \
    tzdata

ENV PATH="/app/.venv/bin:${PATH}"

COPY --from=builder /app /app

ENTRYPOINT ["tini", "--"]
CMD [ "tvhProxy" ]

EXPOSE 5004
