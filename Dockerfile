# Stage 1: build FFmpeg with Intel Quick Sync/VA-API support
FROM ubuntu:24.04 AS ffmpeg-builder

ARG TARGETARCH
RUN if [ "${TARGETARCH:-amd64}" != "amd64" ]; then \
        echo "Intel Quick Sync build is only supported on amd64; requested ${TARGETARCH}" >&2; \
        exit 1; \
    fi

ENV DEBIAN_FRONTEND=noninteractive \
    FFMPEG_VERSION=6.1

RUN printf '%s\n' \
        'deb http://archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse' \
        'deb http://archive.ubuntu.com/ubuntu/ noble-updates main restricted universe multiverse' \
        'deb http://archive.ubuntu.com/ubuntu/ noble-backports main restricted universe multiverse' \
        'deb http://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse' \
    > /etc/apt/sources.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        git \
        libass-dev \
        libaom-dev \
        libdrm-dev \
        libdav1d-dev \
        libmfx-dev \
        libmfx-tools \
        libssl-dev \
        libva-dev \
        libx264-dev \
        libx265-dev \
        nasm \
        pkg-config \
        yasm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src

RUN git clone --depth 1 -b n${FFMPEG_VERSION} https://git.ffmpeg.org/ffmpeg.git ffmpeg

WORKDIR /usr/src/ffmpeg

RUN ./configure \
        --prefix=/usr/local \
        --enable-gpl \
        --enable-nonfree \
        --enable-libaom \
        --enable-libdav1d \
        --enable-libass \
        --enable-libdrm \
        --enable-libmfx \
        --enable-libx264 \
        --enable-libx265 \
        --enable-vaapi \
        --disable-doc \
        --disable-ffplay \
        --disable-ffprobe && \
    make -j"$(nproc)" && \
    make install

RUN rm -rf /usr/src/ffmpeg


# Stage 2: application runtime with compiled FFmpeg
FROM ubuntu:24.04

ARG TARGETARCH
RUN if [ "${TARGETARCH:-amd64}" != "amd64" ]; then \
        echo "Intel Quick Sync runtime is only supported on amd64; requested ${TARGETARCH}" >&2; \
        exit 1; \
    fi

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/bin:$PATH

RUN printf '%s\n' \
        'deb http://archive.ubuntu.com/ubuntu/ noble main restricted universe multiverse' \
        'deb http://archive.ubuntu.com/ubuntu/ noble-updates main restricted universe multiverse' \
        'deb http://archive.ubuntu.com/ubuntu/ noble-backports main restricted universe multiverse' \
        'deb http://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse' \
    > /etc/apt/sources.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        intel-media-va-driver-non-free \
        libass9 \
        libaom3 \
        libdrm2 \
        libdav1d7 \
        libmfx1 \
        libva2 \
        libx264-164 \
        libx265-199 \
        python3 \
        python3-pip \
        python3-venv \
        vainfo \
        wget && \
    python3 -m venv "$VIRTUAL_ENV" && \
    rm -rf /var/lib/apt/lists/*

# Copy FFmpeg from the build stage
COPY --from=ffmpeg-builder /usr/local /usr/local

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir -r requirements.txt && \
    mkdir -p /app/downloads /app/config

# Copy entrypoint script separately to avoid cache invalidation
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Copy application source code
COPY . .

EXPOSE 9833

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "main.py"]
