---
type: regex
match: not_contains
pattern: 'field\s+:price\w*\s*,\s*:float'
target: { source: file, path: lib/my_app/catalog/product.ex }
---
