FROM astral/uv:0.11@sha256:78bc42400d77b0678ba95765305c826652ed5431f399257271dda681d0318f03 AS uv
FROM python:3.14-alpine@sha256:5a824eb82cc75361f98611f3cfc5091ea33f10a6ccea4d4ebdabbc523b9a1614 AS base

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
