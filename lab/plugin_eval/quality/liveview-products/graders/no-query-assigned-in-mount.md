---
type: regex
match: not_contains
pattern: 'assign\(\s*(socket\s*,\s*)?(:products\s*,|products:)\s*(MyApp\.)?Catalog\.'
target: { source: file, path: lib/my_app_web/live/product_index_live.ex }
---
