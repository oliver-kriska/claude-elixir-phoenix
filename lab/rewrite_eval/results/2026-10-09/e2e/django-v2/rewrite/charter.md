# Rewrite Charter

Source: django-realworld (Conduit, RealWorld API spec — Django 1.10.5 + DRF 3.4.4 + PyJWT 1.4.2)

## Goals

- ASSUMED: maintainability — move an unmaintained 2017 Django 1.10 / Python 3.5 stack to a current, supported Elixir/Phoenix stack
- ASSUMED: preserve the RealWorld (Conduit) JSON API contract so existing RealWorld frontends keep working

## Constraints

- ASSUMED: no deadline recorded
- ASSUMED: team Elixir experience unknown — prefer conventional Phoenix/Ecto over clever designs
- ASSUMED: must-keep integrations — the RealWorld HTTP API surface (`/api/...`) and JWT `Authorization: Token <jwt>` header scheme (inventory: PyJWT dep, http-api shape)

## Scope

- Whole app (48 files, 1,778 Python LOC — under the 1,500-file triage cue)

## Steering files

- none found in SOURCE or TARGET (inventory: "Agent-steering files: none found")

## Steering conflicts

- none

## Assumptions

- ASSUMED: Goals — maintainability + RealWorld API compatibility
- ASSUMED: Constraints — no deadline; Elixir experience unknown; keep RealWorld API + JWT token scheme
- ASSUMED: Scope — whole app
