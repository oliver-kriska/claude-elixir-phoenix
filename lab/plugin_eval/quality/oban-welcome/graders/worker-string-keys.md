---
type: regex
pattern: 'args:\s*%\{[^}]*"user_id"\s*=>'
target: { source: file, path: lib/my_app/workers/welcome_email_worker.ex }
---
