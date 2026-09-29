# shellcheck shell=bash
# Sourced by every quality case's scaffold.sh, which `claude plugin eval
# --scaffold` runs in place (so BASH_SOURCE resolves into this repo) with the
# empty eval workspace as the working directory.
#
# Builds the trigger suite's Phoenix fixture, drops the one uncommitted edit it
# leaves for "verify my changes" trigger prompts, and defines seed helpers.

QUALITY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$QUALITY_DIR/../fixture.sh"
git checkout -q -- .

commit() {
  git -c user.email=eval@example.com -c user.name=eval add -A
  git -c user.email=eval@example.com -c user.name=eval commit -q -m "$1"
}

# Catalog context with a float `weight_kg` column: a legitimate float that a
# "follow the existing numeric fields" prompt can pull a price towards.
seed_catalog() {
  mkdir -p lib/my_app/catalog priv/repo/migrations

  cat > lib/my_app/catalog.ex <<'EX'
defmodule MyApp.Catalog do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Catalog.Product

  def list_products, do: Repo.all(from p in Product, order_by: p.name)
  def get_product!(id), do: Repo.get!(Product, id)

  def create_product(attrs) do
    %Product{} |> Product.changeset(attrs) |> Repo.insert()
  end

  def update_product(%Product{} = product, attrs) do
    product |> Product.changeset(attrs) |> Repo.update()
  end
end
EX

  cat > lib/my_app/catalog/product.ex <<'EX'
defmodule MyApp.Catalog.Product do
  use Ecto.Schema
  import Ecto.Changeset

  schema "products" do
    field :name, :string
    field :sku, :string
    field :weight_kg, :float
    field :stock, :integer, default: 0
    timestamps()
  end

  def changeset(product, attrs) do
    product
    |> cast(attrs, [:name, :sku, :weight_kg, :stock])
    |> validate_required([:name, :sku])
    |> validate_number(:stock, greater_than_or_equal_to: 0)
    |> unique_constraint(:sku)
  end
end
EX

  cat > priv/repo/migrations/20260901000000_create_products.exs <<'EX'
defmodule MyApp.Repo.Migrations.CreateProducts do
  use Ecto.Migration

  def change do
    create table(:products) do
      add :name, :string, null: false
      add :sku, :string, null: false
      add :weight_kg, :float
      add :stock, :integer, default: 0, null: false
      timestamps()
    end

    create unique_index(:products, [:sku])
  end
end
EX
}
