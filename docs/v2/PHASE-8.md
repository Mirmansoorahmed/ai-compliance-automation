# Phase 8 — deployable package

> Northwind Advisory for Halvaro Payments GmbH (fictional). Phase 8 packages the policy service so it runs on a clean machine and ships a signed policy bundle. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 8 adds

- **Container entry** (`python -m aca.guard.api`) — serves `/v1/labels` and `/v1/check` with a live Guard (hashed-fallback embedder offline, MiniLM when the `embeddings` extra is present), binding to `0.0.0.0` with host/port/profile from the environment.
- **Dockerfile** (`deploy/docker/Dockerfile`) — a small `python:3.11-slim` image, oss profile (standard library only, no install step), non-root user, `/healthz` healthcheck.
- **docker-compose** (`deploy/docker/docker-compose.yml`) — the policy service plus an OPA server that loads the compliance Rego bundle (`check` / `tier` / `deploy` packages + catalog/obligations data). `docker compose up` on a clean machine runs the full offline story.
- **OPA bundle manifest** (`policy/.manifest`) — roots the bundle at the `compliance` package for `opa build`.
- **Release workflow** (`.github/workflows/release.yml`) — on a version tag, builds the policy-service image and a signed OPA bundle and publishes both to GHCR, keyless-signed with cosign via GitHub OIDC (no stored key). Tag-gated; nothing publishes from a branch.
- **Optional Azure Container Apps IaC** (`deploy/azure/containerapp.bicep`) — docs + Bicep only, region pinned to **Germany West Central** (EU data residency). Never deployed by this repo.

## Run it

Offline, without Docker (same server the container runs):

```bash
make check-stack-demo        # or: scripts/demo_stack.sh
```

Output:

```
GET /healthz -> {'status': 'ok', 'api_version': 'v1'}
POST /v1/check [social scoring] -> BLOCK  rules: AIA-5-1-c
POST /v1/check [fraud score]    -> ALLOW  rules: (none)
POST /v1/check [secret in a diff] -> BLOCK  rules: SEC-SECRETS
```

With Docker (to be run by the owner — Docker is not available in the build sandbox):

```bash
docker compose -f deploy/docker/docker-compose.yml up --build
# policy service on :8080, OPA bundle server on :8181
curl -s localhost:8080/healthz
```

## To be run by the owner

- **`docker compose up`** on a machine with Docker — builds the image and runs the service + OPA. The sandbox has no Docker, so the stack is verified here only in-process (the identical server entry).
- **Tag a release** (`git tag v2.x && git push --tags`) to run `release.yml`: it builds and **keyless-signs** the image and OPA bundle and pushes them to GHCR. This repo does not push images itself.
- **Azure Container Apps** — deploy `deploy/azure/containerapp.bicep` to Germany West Central only with an explicit go, a budget alert set first, and the resource group deleted after. It is never deployed automatically.

## Limits

- **Offline profile.** The image defaults to the oss profile (hashed-fallback embedder) so it runs with no model download; install the `embeddings` extra and set the profile for the real MiniLM model.
- **The OPA server in compose serves the Rego for evaluation/transparency;** the policy service also mirrors the decisions in-process, so the stack works even if OPA is not queried.
- **Signing and registry pushes are owner-run** via the tag workflow; no credentials or images are produced by this build.

## Scope note

Phase 8 is the end of the v2 plan: the whole chain — editor, CI, deploy, runtime, evidence — packaged to run on a clean machine, with a signed policy bundle ready for the owner to publish.
