# shellcheck shell=bash
# flavor: ash — turn the app into an Ash project (detect-ash hook fires on it).
sed -i.bak 's/{:oban, "~> 2.19"}/{:oban, "~> 2.19"},\n      {:ash, "~> 3.5"},\n      {:ash_postgres, "~> 2.6"},\n      {:ash_phoenix, "~> 2.3"}/' mix.exs && rm -f mix.exs.bak
mkdir -p lib/my_app/blog

cat > lib/my_app/blog.ex <<'EX'
defmodule MyApp.Blog do
  use Ash.Domain

  resources do
    resource MyApp.Blog.Post
    resource MyApp.Blog.Comment
  end
end
EX

cat > lib/my_app/blog/post.ex <<'EX'
defmodule MyApp.Blog.Post do
  use Ash.Resource, domain: MyApp.Blog, data_layer: AshPostgres.DataLayer

  postgres do
    table "posts"
    repo MyApp.Repo
  end

  attributes do
    uuid_primary_key :id
    attribute :title, :string, allow_nil?: false
    attribute :body, :string
    timestamps()
  end

  relationships do
    belongs_to :author, MyApp.Accounts.User
    has_many :comments, MyApp.Blog.Comment
  end

  actions do
    defaults [:read, :destroy, create: [:title, :body], update: [:title, :body]]
  end
end
EX

cat > lib/my_app/blog/comment.ex <<'EX'
defmodule MyApp.Blog.Comment do
  use Ash.Resource, domain: MyApp.Blog, data_layer: AshPostgres.DataLayer

  postgres do
    table "comments"
    repo MyApp.Repo
  end

  attributes do
    uuid_primary_key :id
    attribute :body, :string, allow_nil?: false
  end

  relationships do
    belongs_to :post, MyApp.Blog.Post
  end

  actions do
    defaults [:read, create: [:body]]
  end
end
EX
