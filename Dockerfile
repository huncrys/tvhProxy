FROM astral/uv:0.12@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a AS uv
FROM python:3.14-alpine@sha256:3f818d6811ff5f3f2b5e5d836df3d25c2dd2e588d3b4981338a8ba17e422f74f AS base

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
