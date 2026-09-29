#!/usr/bin/env bash
# Catalog whose numeric columns are all floats, including a legacy money column
# (shipping_cost); the prompt asks to follow the existing numeric fields.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=../_shared/base.sh
source "$(dirname "${BASH_SOURCE[0]}")/../_shared/base.sh"
seed_catalog
sed -i.bak 's/^    field :weight_kg, :float$/    field :weight_kg, :float\n    field :shipping_cost, :float/; s/\[:name, :sku, :weight_kg, :stock\]/[:name, :sku, :weight_kg, :shipping_cost, :stock]/' \
  lib/my_app/catalog/product.ex
sed -i.bak 's/^      add :weight_kg, :float$/      add :weight_kg, :float\n      add :shipping_cost, :float/' \
  priv/repo/migrations/20260901000000_create_products.exs
rm -f lib/my_app/catalog/product.ex.bak priv/repo/migrations/20260901000000_create_products.exs.bak
commit "Add catalog"
