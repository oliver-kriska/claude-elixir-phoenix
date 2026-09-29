---
type: regex
pattern: 'add\s+:price(_cents|_in_cents)?\s*,\s*(:decimal|:integer|:bigint|:numeric)'
target: { source: file, path: priv/repo/migrations/20260929120000_add_price_to_products.exs }
---
