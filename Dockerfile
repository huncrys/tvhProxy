FROM astral/uv:0.11@sha256:b1e699368d24c57cda93c338a57a8c5a119009ba809305cc8e86986d4a006754 AS uv
FROM python:3.14-alpine@sha256:01f125438100bb6b5770c0b1349e5200b23ca0ae20a976b5bd8628457af607ae AS base

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
