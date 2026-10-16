# Architecture

One stateless boundary module: HealthRouter. Routing maps to Plug; no domain process or repository is needed.
ADR-001 is authoritative for this slice. Process table: the external host owns the HTTP server; no process is created in this module.
Transactions, jobs, edge codecs and data migration are not applicable to the two stated contracts, not unexamined omissions.
