---
type: regex
pattern: '\{:cancel|:discard|nil\s*->'
target: { source: file, path: lib/my_app/workers/welcome_email_worker.ex }
---
