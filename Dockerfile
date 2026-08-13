FROM astral/uv:0.12@sha256:d0a6eca6c669dc7e9c51218707b8438a3d30402733d739dcc00adb3e213e8f5c AS uv
FROM python:3.14-alpine@sha256:05b2b8b732ecd268fee8727a369f936f022d1321b59befd13c30ede22769dcdc AS base

FROM base AS builder

COPY --from=uv /uv /uvx /usr/local/bin/

RUN apk add --no-cache --update \
    # for uv-dynamic-versioning
    git

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY ./pyproject.toml ./uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . /app
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
