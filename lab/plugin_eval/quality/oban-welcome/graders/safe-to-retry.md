---
type: regex
pattern: 'unique:|sent_at|already'
flags: i
target: { source: file, path: lib/my_app/workers/welcome_email_worker.ex }
---
