---
type: regex
match: not_contains
pattern: 'add\s+:price\w*\s*,\s*:float'
target: { source: file, path: priv/repo/migrations/20260929120000_add_price_to_products.exs }
---
