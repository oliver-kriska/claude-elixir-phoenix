---
type: regex
pattern: 'field\s+:price(_cents|_in_cents)?\s*,\s*(:decimal|:integer|Money\.Ecto)'
target: { source: file, path: lib/my_app/catalog/product.ex }
---
