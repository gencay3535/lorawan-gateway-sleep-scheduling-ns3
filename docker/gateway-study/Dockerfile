FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV MPLCONFIGDIR=/tmp/matplotlib

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    ccache \
    cmake \
    g++ \
    gcc \
    git \
    libgsl-dev \
    libsqlite3-dev \
    libxml2 \
    libxml2-dev \
    ninja-build \
    pkg-config \
    python3 \
    python3-dev \
    python3-matplotlib \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/ns-3-dev

CMD ["/bin/bash"]
