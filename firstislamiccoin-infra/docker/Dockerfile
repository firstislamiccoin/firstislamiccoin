# FirstIslamicCoin node image (headless: firstislamiccoind, -cli, -tx).
#
# Build context is firstislamiccoin-core/, so the image is exactly the checked-out
# tree and nothing else in the monorepo (in particular not secrets/):
#
#   docker build -f firstislamiccoin-infra/docker/Dockerfile -t fic-node firstislamiccoin-core
#
# Adapted from CAC's docker/Dockerfile: same Debian bookworm toolchain and SQLite
# (descriptor) wallet without Berkeley DB; adds a ccache mount so rebuilds after
# small changes are quick, and a `tools` target with Python for the testnet scripts.

FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libtool autotools-dev automake pkg-config bsdmainutils \
        python3 ccache libevent-dev libboost-dev libsqlite3-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . /src/
# A context sent from a Windows checkout does not reliably carry executable bits.
RUN find . -name '*.sh' -exec chmod +x {} +

ENV CCACHE_DIR=/ccache
RUN --mount=type=cache,target=/ccache \
    ./autogen.sh \
    && ./configure --without-gui --disable-bench --disable-tests --disable-fuzz-binary \
         --with-sqlite=yes --without-bdb --enable-ccache \
    && make -j"$(nproc)" \
    && strip src/firstislamiccoind src/firstislamiccoin-cli src/firstislamiccoin-tx

FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        libevent-2.1-7 libevent-pthreads-2.1-7 libsqlite3-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash firstislamiccoin

COPY --from=builder /src/src/firstislamiccoind /src/src/firstislamiccoin-cli /src/src/firstislamiccoin-tx /usr/local/bin/

USER firstislamiccoin
WORKDIR /home/firstislamiccoin
RUN mkdir -p /home/firstislamiccoin/.firstislamiccoin
VOLUME ["/home/firstislamiccoin/.firstislamiccoin"]

# mainnet P2P/RPC, testnet P2P/RPC
EXPOSE 19770 19771 29770 29771

ENTRYPOINT ["firstislamiccoind"]
CMD ["-testnet", "-printtoconsole"]

# Operator tools: the CLI plus Python 3 for the testnet bootstrap, monitor and
# stress scripts, which talk to the nodes over JSON-RPC. Never runs a node.
FROM debian:bookworm-slim AS tools

RUN apt-get update && apt-get install -y --no-install-recommends \
        libevent-2.1-7 libevent-pthreads-2.1-7 libsqlite3-0 python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/src/firstislamiccoin-cli /usr/local/bin/
COPY --from=builder /src/scripts/audit_premine_supply.py /opt/fic/audit_premine_supply.py
WORKDIR /work
