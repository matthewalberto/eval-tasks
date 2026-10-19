# Pinned by digest so the task builds the same image every time.
FROM python:3.12.7-slim-bookworm@sha256:60d9996b6a8a3689d36db740b49f4327be3be09a21122bd02fb8895abb38b50d

# Terminal agents (Harbor's terminus) drive the container through tmux. The task runs with
# no network, so the agent cannot install it at run time; install it at build time instead.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/ /app/
