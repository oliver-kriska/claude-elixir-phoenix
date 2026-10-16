# Analysis Budget

Scope: whole app (`conduit/`, `manage.py`, `requirements.txt`). HISTORY=absent (1 commit, shallow; hotspots suppressed).

| Analyst | Scope paths | Max files read | Max bytes read | History depth | Stop when |
|---------|-------------|----------------|----------------|---------------|-----------|
| feature-cartographer | whole app | 200 | 1 MB | — | budget hit or every surface mapped |
| mechanism-archaeologist | whole app | 200 | 1 MB | 0 (HISTORY=absent) | budget hit or every probe run |
| infra-topologist | deploy/config files + whole app | 100 | 0.5 MB | — | budget hit or every process typed |
| contract-surveyor | schema, routes, config + whole app | 200 | 1 MB | — | budget hit or every surface listed |
