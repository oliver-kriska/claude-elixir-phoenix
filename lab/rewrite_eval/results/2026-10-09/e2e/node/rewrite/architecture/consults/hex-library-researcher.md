# Consult: hex-library-researcher (C-11, C-31, C-32, C-35)

Date: 2026-10-09. Sources read: SOURCE `package.json`, `package-lock.json`, `src/main.ts`,
`src/app/routes/article/article.service.ts:178,317`. Upstream source was taken from the npm registry tarballs
(slugify 1.6.6, cors 2.8.5, body-parser 1.20.2, express 4.18.2, etag 1.8.1, fresh 0.5.2) and Hex tarballs
(slugify 1.3.1, slugger 0.3.0, slugy 4.1.1, cors_plug 3.0.3, corsica 2.1.3, etag_plug 1.0.0). Everything was
unpacked in `/tmp/slugres`, outside the legacy repo. Nothing was executed.

Locked versions (package-lock): slugify **1.6.6**, cors **2.8.5**, express **4.18.2**, body-parser **1.20.2**,
qs **6.11.0**, raw-body 2.5.2, etag **1.8.1**. The Docker image is `node:lts-alpine`, which is **unpinned**,
so V8 error-message text changes whenever the image is rebuilt (this matters for Q3).

---

## Q1. Slugs (C-11): no Hex package matches. Write an in-repo port.

### Hex candidates (all rejected)

| Package | Version / last release | Downloads | Why it does not match |
|---|---|---|---|
| [slugify](https://hex.pm/packages/slugify) (jayjun, module `Slug`) | 1.3.1 / 2020-06 | 5.1M | Lowercases by default (`lowercase: false` exists). Strips all `[:punct:]`, so it drops the `$*_+~.()'"!:@` that legacy keeps. Transliterates with its own table, so `&` does not become `and` and `$` does not become `dollar`. It may transliterate CJK, which legacy deletes (unverified). Last release was more than 12 months ago. |
| [slugger](https://hex.pm/packages/slugger) | 0.3.0 / 2018-06 | 2.3M | Keeps only `[A-Za-z0-9가-힣]` and uses a different replacement table. Abandoned. |
| [slugy](https://hex.pm/packages/slugy) | 4.1.1 / 2021-06 | 0.57M | Built on Unidecode and lowercases. Last release was more than 12 months ago. |

None of them reproduces the npm charMap. All of them delete punctuation that legacy keeps. Example: for
`"Hello, World! (2024) & $5"`, legacy gives `Hello-World!-(2024)-and-dollar5`, while the Hex libraries give
something like `Hello-World-2024-5`.

### Recommendation

Add a project-owned module, e.g. `Realworld.Slug.slugify/1`, that ports slugify 1.6.6 with **default options**.
Build the charMap at compile time from a vendored JSON copy of the npm table. Use `@external_resource` if it is
read from a file. Prove it with golden fixtures.

### Exact algorithm (slugify 1.6.6 `slugify.js`, default options: no locale, `replacement: "-"`, `trim: true`, `strict` and `lower` off)

1. If the input is not a string, throw `Error('slugify: string argument expected')`. In legacy that surfaces as a
   500 with body `"slugify: string argument expected"`, e.g. for `title: 123`. A JSON number is truthy, so it
   passes the `if (!title)` check.
2. `string.normalize()` gives **NFC**. The Elixir equivalent is `:unicode.characters_to_nfc_binary/1`. The
   Unicode versions of Node ICU and OTP can differ on rare code points (unverified).
3. `.split('')` splits into **UTF-16 code units**. For each unit:
   - `appendChar = charMap[ch]`, or `ch` itself if it is not in the map. All charMap keys are in the BMP.
   - **If `appendChar === "-"`, it becomes `" "`.** This catches a literal `-` and also `–` (en dash), whose
     map value is `-`. Hyphens therefore collapse with the surrounding whitespace.
   - The accumulated string is run through the removal regex `/[^\w\s$*_+~.()'"!\-:@]+/g`.
4. The removal regex has no `u` flag, so:
   - `\w` is ASCII only: `[A-Za-z0-9_]`.
   - `\s` is the **JS whitespace set**: `\t \n \v \f \r`, space, U+00A0, U+1680, U+2000–U+200A, U+2028,
     U+2029, U+202F, U+205F, U+3000, U+FEFF.
   - Everything else is removed. That includes unmapped non-ASCII letters, CJK, and emoji. Emoji are surrogate
     pairs, and each half fails the class on its own.

   Because the regex runs on every step and all charMap values only contain allowed characters, this is
   equivalent to filtering per code point. An Elixir port can iterate code points. An astral code point is never
   in the map and is always removed, which gives the same result as dropping its surrogate halves.
5. `slug.trim()` uses JS trim, which removes the same whitespace set plus line terminators.
6. `slug.replace(/\s+/g, "-")` collapses each run of whitespace into a single `-`.
7. No lowercasing. Case is preserved.
8. The caller appends `-${authorId}`. An all-removed title (e.g. `"!!!"` or emoji only) gives the slug `-5`.

Elixir pitfalls:
- Do not use `String.trim/1` or PCRE `\s`/`[:space:]` with the `u` flag. Their whitespace sets differ from JS:
  PCRE/Unicode includes U+0085 NEL and leaves out U+FEFF. Use an explicit character class with the JS set above.
- The charMap contains multi-character values with spaces, such as `"₣" => "french franc"` and
  `"₹" => "indian rupee"`. Their spaces become `-` in step 6. It also contains values with quotes:
  `"“" => "\""`, `"‘" => "'"`, `"Օ" => "O''"`. Keep the table verbatim, including the 3 empty-string mappings
  (`Ь`, `ь`, `ْ`).
- Do not include the `locales` table. Default options never use it.

Minimal shape (illustration only):
```elixir
def slugify(title) when is_binary(title) do
  title
  |> :unicode.characters_to_nfc_binary()
  |> String.to_charlist()
  |> Enum.map_join(fn cp ->
    case Map.get(@char_map, cp, <<cp::utf8>>) do
      "-" -> " "
      s -> s
    end
  end)
  |> String.replace(@remove_re, "")   # explicit ASCII \w + JS-\s class + $*_+~.()'"!\-:@
  |> js_trim()
  |> String.replace(@js_ws_run_re, "-")
end
```

### Golden corpus

Generate fixtures **outside the legacy repo**: `npm i slugify@1.6.6 --ignore-scripts` in a scratch dir, plus a
10-line node script that reads `titles.json` and writes `slug_fixtures.json` with `{input, output}` pairs. Commit
the JSON under `test/fixtures/` and the script under `test/support/`.

Cover these cases:
- ASCII and mixed case
- every charMap category: currency, `&%<>|`, Latin-1, Latin Extended, Greek, Cyrillic, Armenian, Arabic, Persian
  digits, Georgian, Vietnamese
- smart quotes, `–`, `…`, `™`
- all kept punctuation `$*_+~.()'"!:@`
- leading, trailing and multiple hyphens and spaces
- NBSP, U+3000, U+FEFF, U+0085 (the last should be **removed**, not treated as a separator)
- tabs and newlines
- CJK, emoji, ZWJ sequences, combining marks (NFD input, so NFC matters)
- empty-after-strip input
- titles of 1–2k characters

Aim for about 30 hand-picked cases, plus about 500 random strings drawn from the charMap keys. A test should
assert byte equality for every case. Optionally, also diff against real slugs from a production DB snapshot
(strip the `-id` suffix and re-slug the stored titles).

---

## Q2. CORS (C-31): neither plug matches exactly. Write a ~25-line custom plug.

What cors 2.8.5 `cors()` does with defaults (`origin:'*'`, `methods:'GET,HEAD,PUT,PATCH,POST,DELETE'`,
`optionsSuccessStatus:204`, `preflightContinue:false`):

- **Every `OPTIONS` request counts as a preflight.** It does not check for `Origin` or
  `Access-Control-Request-Method`. The response is:
  - status **204** with `Content-Length: 0`, and the router is never reached
  - `Access-Control-Allow-Origin: *`
  - `Access-Control-Allow-Methods: GET,HEAD,PUT,PATCH,POST,DELETE`
  - `Vary: Access-Control-Request-Headers`
  - `Access-Control-Allow-Headers: <request's Access-Control-Request-Headers, verbatim>`, **only if** that
    request header is present
  - no `Max-Age`, no `Allow-Credentials`, no `Expose-Headers`

  Express also adds `X-Powered-By: Express`. The preflight uses `res.end`, so it carries no ETag.
- **Any other method:** only `Access-Control-Allow-Origin: *`, even when the request has no `Origin` header.

Hex options:

| Plug | Version / release | Gap |
|---|---|---|
| [cors_plug](https://hex.pm/packages/cors_plug) | 3.0.3 / 2022-03, 47M downloads | Defaults are `credentials: true`, a fixed header list, `max_age 1728000`, and methods that include `OPTIONS` but leave out `HEAD`. You can configure `credentials: false`, `headers: ["*"]` (which reflects the request header) and `methods: ~w(GET HEAD PUT PATCH POST DELETE)`. It still always sends `access-control-expose-headers` (empty) and `access-control-max-age`. It **passes through an OPTIONS request that has no `Access-Control-Request-Method`** instead of returning 204. It does not send `Vary: Access-Control-Request-Headers`. No release for more than 12 months. |
| [corsica](https://hex.pm/packages/corsica) | 2.1.3 / 2023-10, 10.5M downloads | Answers preflights with **200** by default. Validates requested headers and methods, and drops the CORS headers on a mismatch. Only reflects with `allow_headers: :all`. Spec-correct, but different from legacy. |

**Recommendation:** write a custom `RealworldWeb.Plugs.ExpressCors` plug placed first in the endpoint, before
`Plug.Parsers`. On `OPTIONS` it sets the headers above and calls `send_resp(204, "") |> halt()`. On every other
method it calls `put_resp_header("access-control-allow-origin", "*")`. Cover it with a contract test that compares
headers against legacy (C-31 verification).

A library adds nothing here. Exact parity would need wrapper code anyway, which is more than the plug itself.
If exact preflight parity is relaxed later, use corsica, which has the more recent release.

---

## Q3. Body parsing (C-32)

### Config

```elixir
plug Plug.Parsers,
  parsers: [:urlencoded, :json],
  pass: ["*/*"],            # body-parser ignores other types; req.body = {}
  json_decoder: Jason,      # or JSON (Elixir >= 1.18)
  length: 102_400           # "100kb" in the bytes lib = 100 * 1024
```

Plug.Conn.Query decodes `user[email]=a&user[password]=b` into
`%{"user" => %{"email" => "a", "password" => "b"}}`, so C-32's form-login case works. The current version is
[plug](https://hex.pm/packages/plug) 1.20.3, released 2026-07.

### Differences from body-parser 1.20.2 and qs 6.11.0

The extended urlencoded parser calls qs with `depth: Infinity`, `parameterLimit: 1000`,
`arrayLimit: max(100, count)` and `allowPrototypes: true`. The differences:

- **The error path is the big one.** Every body-parser error reaches the app's error handler in `main.ts`. Those
  errors are `http-errors` objects with `status`, but no `errorCode`, and their `name` is not
  `UnauthorizedError`. So the handler falls through to `res.status(500).json(err.message)`. As a result:
  - malformed JSON gives **500** with a JSON-string body holding the V8 `SyntaxError` message, e.g.
    `"Unexpected token } in JSON at position 9"`. The wording depends on the Node version: Node 20+ says
    `Expected property name or '}' ...`.
  - a body over 100kb gives **500** with body `"request entity too large"`, **not 413**. **C-32's "→ 413" looks
    wrong**, and the characterization run should confirm it.
  - more than 1000 urlencoded params give 500 with `"too many parameters"`.
  - a non-utf charset gives 500 with `unsupported charset "X"`.

  Plug raises `Plug.Parsers.ParseError` (400), `RequestTooLargeError` (413) and `UnsupportedMediaTypeError`
  (415). To keep parity, wrap `Plug.Parsers` in a project plug that rescues these exceptions and sends 500 with
  `Jason.encode!(message)` as `application/json; charset=utf-8`.

  **Do not try to match the V8 message text.** It is not reproducible, and it already drifts with the unpinned
  `node:lts-alpine` image. Compare status and content type only. Record this as an ADR relaxation.
- **Strict JSON.** body-parser rejects a top-level value that is not an object or array, based on its first
  character, and that becomes 500. Plug accepts it and wraps it as `%{"_json" => v}`. Plug also wraps top-level
  arrays as `%{"_json" => [...]}`, while legacy keeps them as arrays. Either way the envelope is missing, so the
  port's missing-envelope path (register 422, login and comment 500) must also fire for `_json`-wrapped bodies.
  Add a rejection for non-object JSON if strictness matters.
- **Empty JSON body** gives `{}` in both.
- **qs vs Plug.Conn.Query** (edge cases only, unverified beyond source reading):
  - `a=1&a=2`: qs gives `["1","2"]`, Plug keeps the last value.
  - `a[0]=x`: qs gives an array, Plug gives `%{"0" => "x"}`.
  - Plug has no parameter limit and no 1000-param 500.

  Legacy feeds such values into Prisma and gets a 500 anyway, so this is low risk. List them in the contract
  notes rather than port qs.
- **Content-Type matching:** body-parser's json type is exactly `application/json` (via type-is), so
  `application/*+json` is not parsed. Plug's `:json` parser also accepts `+json` (unverified). This difference is
  minor.

---

## Q4. Weak ETag + 304 (C-35): write a tiny custom plug. Keeping it is optional but cheap.

What Express 4.18.2 does (`etag` setting defaults to `'weak'`, `res.send`):

- For **every** `res.send`/`res.json` with a body, whatever the method or status (POST, 4xx and 500 included),
  it sets `ETag: W/"<byteLength hex>-<base64(sha1(body))[0..26]>"`. For an empty body the value is
  `W/"0-2jmj7l5rSw0yVb/vlWAYkK/YBwk"`.
- `req.fresh` is checked only for **GET/HEAD** with status 2xx or 304. It uses fresh 0.5.2:
  - `Cache-Control: no-cache` in the request disables it
  - `If-None-Match: *` matches
  - otherwise it is a weak comparison against the list (exact rules partly unverified)
- When fresh, the status becomes **304**, `Content-Type` and `Content-Length` are removed, and the body is
  dropped. HEAD also drops the body.

Hex: [etag_plug](https://hex.pm/packages/etag_plug) 1.0.0 (2020-10, 230k downloads) is stale. It emits
hex-encoded strong tags and only covers configured methods and statuses, so it does not match. Plug core has
ETags only for `Plug.Static`. phoenix_etag is schema-based and does not apply here.

**Recommendation:** write a project plug, `RealworldWeb.Plugs.ExpressETag`, of about 30 lines using
`register_before_send/2`:
- take `IO.iodata_to_binary(conn.resp_body)` and compute the tag as above: `:crypto.hash(:sha, body)`, then
  `Base.encode64`, then `binary_part(…, 0, 27)`, with the length as lowercase hex
- set the header whenever the body is not chunked or sent with sendfile
- for GET/HEAD with 2xx and a matching `If-None-Match`, rewrite to 304 with an empty body and delete
  `content-type`

`X-Powered-By: Express` can live in the same plug.

**Is it worth keeping?** Optional. Dropping it only costs bandwidth: clients get 200 instead of 304, and no
correctness depends on it. It is cheap and deterministic, though, and it lets a header-diff harness against legacy
pass without exclusions. Default: **keep**, with an ADR note that it may be dropped. If it is dropped, exclude
`ETag` and `X-Powered-By` from the contract diff.

---

## Compatibility notes

- All recommendations need only `plug` (1.20.x) plus `jason`, or the stdlib `JSON` on Elixir ≥ 1.18. No new Hex
  dependencies.
- Plug order in the endpoint: ExpressCors → ExpressETag (before_send) → wrapped Plug.Parsers → router.
- Open characterization items:
  - the 413-vs-500 behaviour for oversized bodies (C-32 claim)
  - the exact Node version in production (it decides the SyntaxError text, which should be excluded anyway)
  - Unicode NFC version drift between Node ICU and OTP for exotic code points
