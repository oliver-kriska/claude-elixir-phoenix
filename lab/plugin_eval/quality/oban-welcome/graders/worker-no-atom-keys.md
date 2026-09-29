---
type: regex
match: not_contains
pattern: 'args:\s*%\{[^}]*\buser_id:'
target: { source: file, path: lib/my_app/workers/welcome_email_worker.ex }
---
