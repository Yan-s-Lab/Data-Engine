# Label Studio Third-Party Bootstrap (2026-02-28)

## Background

- Requirement: add Label Studio as a repository-managed third-party service.
- Existing installation baseline from project owner:
  - `docker pull heartexlabs/label-studio:latest`
  - `docker run -it -p 8080:8080 -v $(pwd)/mydata:/label-studio/data heartexlabs/label-studio:latest`

## Changes

1. Added `third_party/label_studio/docker-compose.label-studio.yml`
- Runs `heartexlabs/label-studio:latest` as `label-studio` service.
- Exposes host port `${LABEL_STUDIO_PORT:-8080}` to container `8080`.
- Persists data at `data/label_studio` via bind mount to `/label-studio/data`.
- Adds container healthcheck on `http://127.0.0.1:8080/api/health`.

2. Added `third_party/label_studio/label_studio_ctl.sh`
- Unified control surface: `ensure|status|check|start|stop|logs`.
- `ensure` checks service health first, then starts via docker compose if unavailable.
- `check` validates runtime reachability on configured host port.

3. Added `third_party/label_studio/.env.example`
- Supports image/container/port overrides:
  - `LABEL_STUDIO_IMAGE`
  - `LABEL_STUDIO_CONTAINER_NAME`
  - `LABEL_STUDIO_PORT`

4. Updated `README.md`
- Added Label Studio bootstrap commands to quickstart prepare section.

## Usage

```bash
cp third_party/label_studio/.env.example third_party/label_studio/.env
./third_party/label_studio/label_studio_ctl.sh ensure
./third_party/label_studio/label_studio_ctl.sh check
```

Equivalent default URL: `http://127.0.0.1:8080`
