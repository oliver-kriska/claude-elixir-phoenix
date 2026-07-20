# PostgreSQL Full-Text Search with Ecto

Native full-text search without external dependencies. Based on
[Search is Not Magic with PostgreSQL](https://www.codecon.sk/search-is-not-magic-with-postgresql).

## Strategy Decision Tree

| Need | Strategy | Extension |
|------|----------|-----------|
| Exact/weighted text search | Full-text search (tsvector) | Built-in |
| Typo tolerance / fuzzy | Trigram similarity (pg_trgm) | `pg_trgm` |
| Semantic / AI search | Vector search (pgvector) | `pgvector` |
| All of the above | Hybrid with RRF | Multiple |

## 1. Full-Text Search (tsvector/tsquery)

### Migration — Generated Column (Preferred, PostgreSQL 12+)

```elixir
def up do
  execute """
  ALTER TABLE articles
    ADD COLUMN searchable tsvector
    GENERATED ALWAYS AS (
      setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
      setweight(to_tsvector('english', coalesce(body, '')), 'B')
    ) STORED;
  """

  create index(:articles, [:searchable], using: :gin)
end

def down do
  alter table(:articles) do
    remove :searchable
  end
end
```

Generated columns auto-update on INSERT/UPDATE — no triggers needed.

**When to use triggers instead**: When the tsvector depends on associated
records (e.g., tags from a join table). Generated columns can only reference
columns in the same row.

### Basic Search Query

```elixir
def search_articles(query_string) do
  from(a in Article,
    where: fragment(
      "searchable @@ websearch_to_tsquery('english', ?)",
      ^query_string
    ),
    order_by: [desc: fragment(
      "ts_rank_cd(searchable, websearch_to_tsquery('english', ?), 32)",
      ^query_string
    )]
  )
  |> Repo.all()
end
```

### Search with Highlights and Pagination

```elixir
def search_articles(query_string, opts \\ []) do
  page = Keyword.get(opts, :page, 1)
  per_page = Keyword.get(opts, :per_page, 20)

  from(a in Article,
    where: fragment("searchable @@ websearch_to_tsquery('english', ?)", ^query_string),
    select: %{
      id: a.id,
      title: a.title,
      headline: fragment(
        "ts_headline('english', ?, websearch_to_tsquery('english', ?), 'StartSel=<mark>, StopSel=</mark>')",
        a.body, ^query_string
      ),
      rank: fragment("ts_rank_cd(searchable, websearch_to_tsquery('english', ?), 32)", ^query_string)
    },
    order_by: [desc: fragment("ts_rank_cd(searchable, websearch_to_tsquery('english', ?), 32)", ^query_string)],
    offset: ^((page - 1) * per_page),
    limit: ^per_page
  )
  |> Repo.all()
end
```

### Multi-Language Support

```elixir
# Dynamic language via regconfig casting
from(a in Article,
  where: fragment(
    "to_tsvector(?::text::regconfig, ?) @@ to_tsquery(?::text::regconfig, ?)",
    ^language, a.body, ^language, ^query
  )
)
```

### websearch_to_tsquery Syntax (Google-style)

| Input | Matches |
|-------|---------|
| `elixir phoenix` | Both words |
| `"exact phrase"` | Exact phrase |
| `elixir OR phoenix` | Either word |
| `-deprecated` | Excludes word |

### Weight Meanings

| Weight | Use | Boost |
|--------|-----|-------|
| A | Title | Highest |
| B | Subtitles | High |
| C | Body | Medium |
| D | Metadata | Lower |

## 2. Trigram Similarity (pg_trgm) — Fuzzy/Typo Tolerance

```elixir
# Migration
execute "CREATE EXTENSION IF NOT EXISTS pg_trgm"
execute "CREATE INDEX products_name_trgm_idx ON products USING gin(name gin_trgm_ops)"

# Query
from(p in Product,
  where: fragment("similarity(?, ?) > ?", p.name, ^term, 0.3),
  order_by: [desc: fragment("similarity(?, ?)", p.name, ^term)]
)
```

Trigrams compare 3-character groups — handles typos, misspellings, partial matches.
Threshold 0.3 is a good default; tune based on your data.

## 3. Hybrid Search with RRF (Reciprocal Rank Fusion)

Combine multiple search strategies by normalizing ranks:

```elixir
# Each strategy returns %{id, rank} with: 1 / (60 + distance)
similarity_results = search_by_trigram(term)
fulltext_results = search_by_tsvector(term)

# Merge with deduplication
(similarity_results ++ fulltext_results)
|> Enum.group_by(& &1.id)
|> Enum.map(fn {id, ranks} -> {id, Enum.sum(Enum.map(ranks, & &1.rank))} end)
|> Enum.sort_by(&elem(&1, 1), :desc)
```

### Multi-Word Query Normalization

```elixir
defp normalize_query(text) do
  text
  |> String.trim()
  |> String.downcase()
  |> String.replace(~r/\s+/, " ")
  |> String.split(" ")
  |> Enum.join(" & ")
end
```

## Performance

```elixir
# ALWAYS use GIN index for tsvector
create index(:articles, [:searchable], using: :gin)

# Partial index for large tables
create index(:articles, [:searchable], using: :gin, where: "published_at IS NOT NULL")

# GIN indexes only used with LIMIT — always paginate
```

## Anti-patterns

```elixir
# WRONG: Computing tsvector at query time (slow, no index!)
from(a in Article,
  where: fragment("to_tsvector('english', title || ' ' || body) @@ to_tsquery(?)", ^q)
)

# WRONG: Using LIKE for search (no ranking, no stemming)
from(a in Article, where: ilike(a.title, ^"%#{query}%"))

# WRONG: Using triggers when generated columns suffice
# Generated columns are simpler and auto-maintained

# WRONG: Assuming PG can't do fuzzy search
# pg_trgm handles typo tolerance natively — no need for Elasticsearch just for fuzzy
```

## When to Use External Search

PostgreSQL handles most use cases (100K-10M docs). Consider Meilisearch/Elasticsearch for:

- Faceted search with complex filters across many dimensions
- Multi-language with mixed alphabets in same field
- Real-time indexing of 10M+ documents
- Advanced search analytics

**Further reading**: [Search is Not Magic with PostgreSQL](https://www.codecon.sk/search-is-not-magic-with-postgresql)
— covers trigrams, full-text, vector search, and hybrid patterns with Ecto examples.
