# Elixir 1.20 Type System Reference

> **Blog**: <https://elixir-lang.org/blog/2026/06/03/elixir-v1-20-0-released/>
> **Changelog**: <https://elixir.hexdocs.pm/1.20.0/changelog.html#type-system-improvements>
> **HexDocs**: use `hexdocs-fetcher` for the latest API docs.

## TL;DR

Elixir 1.20 (released 2026-06-03) completed its **first type-system
milestone**: the compiler now infers types and gradually type-checks **every**
program **without any annotations**. It reports **dead/redundant code** and
**verified bugs** — typing violations guaranteed to fail at runtime. Low false
positives by design.

**Requires OTP 27+.** No new struct/typespec syntax — that is a *future*
milestone. There is **nothing new to write**; this release is about
*interpreting new compiler diagnostics*.

## The one thing that changes day-to-day

Type violations are emitted as **`mix compile` warnings** — built into the
compiler. **Not** Dialyzer, **not** a separate tool, **no PLT**.

> On Elixir 1.20+, `mix compile --warnings-as-errors` **now fails the build on
> type violations.** This is what `/phx:verify`, `/phx:work` checkpoints, and
> the "fix CI" pattern run everywhere — so a verified bug becomes a hard
> failure, not a silent warning.

When a `--warnings-as-errors` build that previously passed starts failing after
a toolchain bump to 1.20, **suspect a newly-detected type violation before
assuming the code regressed** — the code didn't change, the checker got smarter.

## The `dynamic()` mental model

Unlike `any()` in most gradual languages ("anything goes, never flag"),
Elixir's `dynamic()` is a **refinable range**:

- **Compatibility** — a call is flagged **only when the supplied and accepted
  types are disjoint**. `dynamic(integer() or binary())` passed to `/` (wants a
  number) is fine — `integer()` overlaps. Passed to `Map.fetch!/2` (wants a
  map) it is flagged — disjoint.
- **Narrowing** — usage refines the type. `data.a + data.b` narrows `data` to
  `%{..., a: number(), b: number()}` (the `...` = "may have other keys").

```elixir
# value_or_error :: dynamic(integer() or binary()) at runtime
Map.fetch!(value_or_error, :some_key)  # ⚠ violation: map ⟂ int|binary

def add_a_and_b(data) do
  data.a + data   # ⚠ data narrowed to %{..., a: number()}, then used AS a number
end
```

## What the checker catches

| Kind | Example that warns |
|------|--------------------|
| **Verified bug** | calling `User.name(%{})` when it needs `%{..., name: term()}` |
| **Disjoint call** | `String.upcase/1` on a value the checker proved is an integer |
| **Dead clause** | a `case` clause that can never match given prior clauses |
| **Bad field access** | `x.foo` after a guard proved `x` has **no** `:foo` key |
| **Out-of-bounds** | `elem(x, 3)` after `tuple_size(x) < 3` |

## Inference you get for free

**Guards** infer unions/intersections/negations:

```elixir
def f(x, y) when is_list(x) and is_integer(y)        # x :: list, y :: integer
def f({:ok, x} = y) when is_binary(x) or is_integer(x)
def f(x) when is_map_key(x, :foo)        # x :: %{..., foo: dynamic()}
def f(x) when not is_map_key(x, :foo)    # x :: %{..., foo: not_set()} → x.foo warns
def f(x) when tuple_size(x) < 3          # elem(x, 3) warns
```

**Clauses / occurrence typing** (`case`, `cond`, `with`) — earlier clauses
refine later ones:

```elixir
case System.get_env("SOME_VAR") do
  nil   -> :not_found
  value -> {:ok, String.upcase(value)}   # value :: binary() (nil already excluded)
end
```

**Maps** track non-atom keys by domain and typed stdlib ops:

```elixir
%{123 => "hello", 456.0 => :ok}   # %{integer() => binary(), float() => :ok}
Map.put(map, :key, 123)           # %{..., key: integer()}
Map.delete(map, :key)             # %{..., key: not_set()}
Map.replace(map, :key, 123)       # %{..., key: if_set(integer())}
```

## How to read & fix a type violation

1. **Read the message literally** — it states the *accepted* vs *supplied*
   type. The fix is to make them overlap, not to silence the warning.
2. **Check the narrowing chain** — the warning usually points at where the
   variable was *refined* (a guard, a prior clause, a field access), not just
   where it blew up.
3. **It is almost always a real bug.** False positives are rare by design
   (disjoint-only). Prefer fixing the code over restructuring to dodge the
   checker.
4. **Genuinely dynamic boundary?** If a value really is runtime-typed
   (external input), the disjoint-only rule already tolerates it — only a
   provably-impossible call warns.

## Compiler type checker vs Dialyzer

They are **different tools** — keep both in mind:

| | Compiler type checker (1.20+) | Dialyzer / dialyxir |
|--|------------------------------|----------------------|
| Runs in | `mix compile` (built-in) | `mix dialyzer` (separate, needs PLT) |
| Setup | none | PLT build (slow first run) |
| Basis | set-theoretic types, `dynamic()` | success typing |
| Annotations | none needed | reads `@spec` |
| Caught by `--warnings-as-errors` | **yes** | no |
| Best at | disjoint calls, dead clauses, map/guard narrowing | `@spec` mismatches, contract violations, opaque misuse |

Guidance: the compiler checker is now the **first line** of type safety and is
always on. Dialyzer remains valuable for `@spec`/contract checking and opaque
types — it is **complementary, not redundant**.

## Bonus: faster compiles

New compiler option `:module_definition` (`:compiled` default, or
`:interpreted`) can speed up large-project builds. Set in `mix.exs`:

```elixir
elixirc_options: [module_definition: :interpreted]
```

Does not change emitted `.beam` files — only how `defmodule` bodies execute at
compile time (slight stacktrace-precision tradeoff).

## Compatibility notes

- Type checking ships in Elixir **1.20+** on **OTP 27+** (compatible to OTP 29).
- No code changes required to benefit — recompile and read the warnings.
- No annotation syntax yet; typed structs and signatures are the next milestone.
- Check version in `mix.exs`: `{:elixir, "~> 1.20"}`.
