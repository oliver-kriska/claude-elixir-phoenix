---
type: regex
pattern: '"?user_id"?\s*(:|=>)\s*\w+\.id'
target: { source: file, path: lib/my_app/accounts.ex }
---
