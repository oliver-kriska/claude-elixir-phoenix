---
description: Build a LiveView over a 50k-row table next to an existing LiveView that queries in mount. Iron Laws 1 and 2 ask for assign_async/connected? and streams.
expected_outcome: ProductIndexLive loads products asynchronously or behind connected?/1, renders them with a stream, and pages instead of loading 50k rows.
tags: [quality, liveview, quick]
max_turns: 25
timeout_seconds: 420
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

/phx:quick Create MyAppWeb.ProductIndexLive in lib/my_app_web/live/product_index_live.ex that
lists every product's name and SKU, in the same style as the existing UserLive. There are about 50,000
products. You may add functions to MyApp.Catalog if you need them. mix is not available here, so don't
compile.
