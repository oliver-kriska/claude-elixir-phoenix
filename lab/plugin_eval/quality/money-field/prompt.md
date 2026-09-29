---
description: Add a price to a schema whose numeric columns, including the legacy shipping_cost, are floats. Iron Law 4 says money is never :float.
expected_outcome: price stored as :decimal or integer cents in both the schema and the migration, cast in the changeset, and the final answer flags shipping_cost as float money.
tags: [quality, ecto, quick]
max_turns: 25
timeout_seconds: 420
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

/phx:quick Add a price to products. Shop admins type prices like 19.99 into the product form. Follow the
conventions of the existing numeric fields on the schema. Put the migration in
priv/repo/migrations/20260929120000_add_price_to_products.exs. mix is not available in this environment, so
don't try to compile.
