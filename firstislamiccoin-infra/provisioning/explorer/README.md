# explorer provisioning

Scripts for deploying `firstislamiccoin-explorer/` to a real server. **Not
deployed anywhere yet** — there is no `explorer.firstislamiccoin.com` DNS
record (see `docs/dns.md`) and no server provisioned in this environment.
This directory is ready-to-run infrastructure, not a record of a real
deployment, unlike CodexaCoin's own equivalent directory.

- `provision.sh` — installs `firstislamiccoind`'s explorer service on a
  fresh Debian/Ubuntu VPS: system deps, a dedicated `fic-explorer` user, a
  Python venv, and a systemd unit. Needs `REPO_URL` (no public
  FirstIslamicCoin GitHub org exists yet) or `SOURCE_DIR` (a local
  checkout), plus either `FIC_RPC_COOKIEFILE` or `FIC_RPC_USER`/
  `FIC_RPC_PASSWORD` for the node it talks to.
- `explorer.service` — the systemd unit `provision.sh` installs (template,
  filled in by the script).
- `nginx-example.conf` — serves the static frontend and reverse-proxies
  `/api/` to the backend under one origin, so no CORS configuration is
  needed for a same-origin deployment.

The actual verification this codebase has been checked against — real,
live testnet data, every number cross-checked against the node's own RPC
output — is in `firstislamiccoin-explorer/README.md`'s "Verification"
section, run through a throwaway container rather than a real host, since
no real server exists here to provision.
