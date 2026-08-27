# Exception Taxonomy for Rescue Narrowing

Verified exception types by work category. Use these as the default sets when narrowing bare
rescues, and add to them only when you can point to a specific call in the rescue body that
raises the extra type.

**Last validated:** 2026-04 against Elixir 1.19 / OTP 28. Libraries occasionally rename
exception modules between minor versions — if you're narrowing against a newer dep, confirm
the names still exist before committing or you'll hit `(CompileError) module is not available`.

All entries were validated against the deps of a production Phoenix codebase during a
rescue-narrowing audit. When a library updates, re-verify by running:

```bash
grep -rn "defexception" deps/<libname>/lib/
```

## Table of contents

1. [JSON encode/decode](#json-encodedecode)
2. [Ecto + Postgres](#ecto--postgres)
3. [Money / Decimal arithmetic](#money--decimal-arithmetic)
4. [File I/O](#file-io)
5. [Req HTTP client](#req-http-client)
6. [ExAws (S3 / SES / etc.)](#exaws-s3--ses--etc)
7. [ExCmd shell subprocess](#excmd-shell-subprocess)
8. [Regex](#regex)
9. [Atoms from strings](#atoms-from-strings)
10. [Phoenix forms + atom conversion](#phoenix-forms--atom-conversion)
11. [Plug request parsing](#plug-request-parsing)
12. [Phoenix LiveView HEEx / MDEx](#phoenix-liveview-heex--mdex)
13. [NimbleCSV](#nimblecsv)
14. [Redlines / DOCX / PDF](#redlines--docx--pdf)
15. [Explicit `raise` in your own code](#explicit-raise-in-your-own-code)
16. [Programmer-bug exceptions to EXCLUDE](#programmer-bug-exceptions-to-exclude)

---

## JSON encode/decode

```elixir
[Jason.DecodeError, Jason.EncodeError, ArgumentError]
```

- `Jason.decode!/1` → `Jason.DecodeError` on bad JSON, `ArgumentError` on non-binary input
- `Jason.encode!/1` → `Jason.EncodeError` on non-encodable term, `Protocol.UndefinedError` for struct without impl
- For Elixir 1.18+ `JSON` (built-in, replaces Jason in new code): same exception types via the same modules — the `JSON` module re-exports Jason internals

Add `Protocol.UndefinedError` when encoding arbitrary structs:

```elixir
[Jason.EncodeError, Protocol.UndefinedError, ArgumentError]
```

## Ecto + Postgres

```elixir
[
  Ecto.NoResultsError,
  Ecto.InvalidChangesetError,
  Ecto.ConstraintError,
  Ecto.StaleEntryError,
  Ecto.Query.CastError,
  Postgrex.Error,
  DBConnection.ConnectionError
]
```

- `Repo.get!/2`, `Repo.one!/1` → `Ecto.NoResultsError`
- `Repo.insert!/1`, `Repo.update!/1` → `Ecto.InvalidChangesetError`
- Unique/foreign key violations → `Ecto.ConstraintError`
- Optimistic lock conflicts → `Ecto.StaleEntryError`
- Parameter type mismatch in queries → `Ecto.Query.CastError`
- Raw Postgres errors (triggers, serialization) → `Postgrex.Error`
- Connection drops or pool exhaustion → `DBConnection.ConnectionError`

When doing bulk inserts/updates, add `ArgumentError` (for row validation failures in `insert_all`).

## Money / Decimal arithmetic

```elixir
[
  ArgumentError,
  ArithmeticError,
  FunctionClauseError,
  Decimal.Error,
  Money.UnknownCurrencyError,
  Money.InvalidAmountError
]
```

- `Decimal.new/1` on a malformed binary → `Decimal.Error`
- `Decimal.div/2` by zero → `ArithmeticError`
- `Money.new/2` with unknown currency code → `Money.UnknownCurrencyError`
- `Money.new/2` with non-numeric amount → `Money.InvalidAmountError`
- Arithmetic on a `nil` that wasn't expected → `ArithmeticError`

Add `Protocol.UndefinedError` when piping into `Decimal.cmp/2` with a term that isn't `Decimal`-comparable.

## File I/O

```elixir
[File.Error, File.CopyError, ErlangError, ArgumentError]
```

- `File.read!/1`, `File.write!/2` → `File.Error`
- `File.cp!/2`, `File.rename!/2` → `File.CopyError`
- Bad path / encoding issues → `ErlangError` or `ArgumentError`

For atomic temp-file writes (`File.write!` then `File.rename!`), include both.

## Req HTTP client

```elixir
[Req.TransportError, Req.HTTPError, Req.DecompressError, ArgumentError]
```

- Network failures (DNS, TCP, TLS) → `Req.TransportError`
- HTTP protocol violations → `Req.HTTPError`
- Gzip/brotli decompression failures → `Req.DecompressError`
- Bad URL → `ArgumentError` (from `URI.parse!/1` inside Req)
- `URI.Error` from `URI.parse!/1` directly — add when you call `URI.parse!/1` yourself

For `Req.request!/1` with `retries: :safe_transient`, still include the transport error — the `!` variant still raises on final failure.

## ExAws (S3 / SES / etc.)

```elixir
[ExAws.Error, MatchError, ArgumentError, ErlangError, Jason.DecodeError]
```

- AWS API errors → `ExAws.Error`
- Pattern match on `{:ok, _}` failing when the API returns `{:error, _}` → `MatchError`
- Response body JSON parse failure → `Jason.DecodeError`

## ExCmd shell subprocess

```elixir
[ExCmd.Stream.AbnormalExit, ErlangError, ArgumentError, MatchError, RuntimeError]
```

- Non-zero exit status from the subprocess → `ExCmd.Stream.AbnormalExit` (**required** in every ExCmd rescue — not caught by any other type)
- Port / OS errors → `ErlangError`
- Malformed command args → `ArgumentError`

Add `ArithmeticError` if the rescue body performs ratio/percentage math on bytes read.

## Regex

```elixir
# Add to any rescue where the body uses Regex.compile*, Regex.run, Regex.replace, or ~r sigils:
[Regex.CompileError]
```

- `Regex.compile!/1` on malformed pattern → `Regex.CompileError`
- `~r/.../` compiled at runtime with user input — same
- `Regex.run/2`, `Regex.replace/3` do not raise on non-match, but can raise if given an invalid pre-compiled regex

## Atoms from strings

```elixir
[ArgumentError]
```

- `String.to_existing_atom/1` on unknown atom → `ArgumentError`
- `String.to_atom/1` is atom-exhaustion dangerous; prefer `to_existing_atom` and catch the ArgumentError

Never write `rescue _ ->` around `String.to_existing_atom` — the ArgumentError on unknown atom is often a legitimate signal (e.g., untrusted input), not an unexpected condition.

## Phoenix forms + atom conversion

```elixir
[ArgumentError, FunctionClauseError, KeyError]
```

Pattern:

```elixir
case Form.input_value(form, :structure_type) do
  val when is_atom(val) -> val
  val when is_binary(val) and val != "" -> String.to_existing_atom(val)
  _ -> nil
end
rescue
  _ in [ArgumentError, FunctionClauseError, KeyError] -> nil
end
```

- `ArgumentError` → `to_existing_atom` on unknown value
- `KeyError` → form missing the field entirely
- `FunctionClauseError` → unexpected form shape

## Plug request parsing

```elixir
[
  ArgumentError,
  MatchError,
  FunctionClauseError,
  CaseClauseError,
  ErlangError,
  Plug.BadRequestError,
  Plug.Conn.InvalidQueryError,
  Plug.Parsers.ParseError,
  Plug.Parsers.BadEncodingError
]
```

- `Plug.Conn.Query.decode/1` on invalid UTF-8 → `Plug.Conn.InvalidQueryError` (**not just ArgumentError**)
- Multipart parse failures → `Plug.Parsers.ParseError`
- Bad Content-Transfer-Encoding → `Plug.Parsers.BadEncodingError`
- Too-large body → `Plug.BadRequestError`

## Phoenix LiveView HEEx / MDEx

```elixir
[
  MatchError,
  ArgumentError,
  RuntimeError,
  FunctionClauseError,
  Phoenix.LiveView.Tokenizer.ParseError,
  MDEx.DecodeError,
  MDEx.InvalidInputError,
  Regex.CompileError
]
```

**Gotcha:** the HEEx tokenizer error lives at `Phoenix.LiveView.Tokenizer.ParseError`, **not** `Phoenix.LiveView.HTMLTokenizer.ParseError`. The latter is a common misremember — no such module exists.

- `MDEx.to_heex!/2` on malformed markdown → `MDEx.DecodeError`
- `MDEx.to_html/1` with bad input → `MDEx.InvalidInputError`
- HEEx template failing to parse after MDEx output → `Phoenix.LiveView.Tokenizer.ParseError`

## NimbleCSV

```elixir
[NimbleCSV.ParseError, MatchError, ArgumentError]
```

**Gotcha:** only `NimbleCSV.ParseError` is public. The RFC4180-specific structs
(`NimbleCSV.RFC4180.RowLengthError`, etc.) are **internal** and will fail to compile if
referenced. Verified by grepping deps:

```bash
grep -rn "defexception" deps/nimble_csv/lib/
# Output: deps/nimble_csv/lib/nimble_csv.ex: defexception [:line, :reason]
```

## Redlines / DOCX / PDF

For `read_word_document.ex`-style code paths:

```elixir
# Extracting text
[ErlangError, ArgumentError]

# Unzipping / copying temp files
[File.Error, File.CopyError, ErlangError, ArgumentError, RuntimeError]

# Processing text with regex
[ArgumentError, Regex.CompileError, FunctionClauseError, KeyError]
```

For `pdftotext_mapper.ex` (ExCmd-based PDF parsing):

```elixir
[ExCmd.Stream.AbnormalExit, ErlangError, ArgumentError, MatchError, RuntimeError, ArithmeticError]
```

The `ArithmeticError` is for bounding-box ratio calculations that can divide by zero on malformed PDFs.

## Explicit `raise` in your own code

If the `try` body calls functions that explicitly `raise RuntimeError` or `raise "msg"` (which creates a `RuntimeError`), add `RuntimeError` to the rescue list.

```elixir
defp validate!(activity) do
  if problem?(activity), do: raise("Migration halted: #{inspect(activity)}")
end

def migrate(activities) do
  Enum.each(activities, &validate!/1)
rescue
  e in [
    Ecto.ConstraintError,
    Ecto.StaleEntryError,
    Postgrex.Error,
    DBConnection.ConnectionError,
    ArgumentError,
    MatchError,
    RuntimeError   # <-- required because validate! explicitly raises
  ] ->
    {:error, e}
end
```

**Forgetting `RuntimeError` here is a common mistake** — the old bare rescue was catching it, and the narrowed version silently changes behavior. Always check for `raise` calls in the call path.

## Programmer-bug exceptions to EXCLUDE

These should almost never appear in a narrowed rescue list, because catching them is precisely what hides the bugs this skill is meant to surface:

| Exception | Why to exclude |
|-----------|---------------|
| `UndefinedFunctionError` | Typo in a module/function name; must propagate |
| `CompileError` | Bad template or macro expansion; must propagate |
| `BadFunctionError` | Calling a non-function; must propagate |
| `BadArityError` | Wrong number of args at a fun call; must propagate |

If a narrowed rescue list includes any of these, re-examine whether the original bare rescue
was genuinely meant to suppress them (rare) or was accidentally hiding bugs (common).

**Exceptions to the exclusion:** `FunctionClauseError` and `ArgumentError` have legitimate
non-bug uses (e.g., `:erlang.binary_to_existing_atom/1` raises `ArgumentError` on unknown
input, which is legitimate data). Include them only when you can point to a call in the body
that raises them as a data signal, not as a programmer error.
