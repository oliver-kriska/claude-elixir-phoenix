## Architectural decisions

### Lazy class registry — deferred

**Decision**: skip the lazy class registry pattern.

**Reference**: Future AGI's `evaluations/engine/registry.py` is the inspiration
we evaluated. It dynamically resolves evaluator classes by string ID, lazily
importing modules on first use.

**Current state**: 8 dimension modules dispatched via an explicit
`DIMENSION_MODULES` dict at `lab/eval/scorer.py:18-27` (completeness, accuracy,
conciseness, triggering, safety, clarity, specificity, behavioral). Matcher
dispatch lives in `lab/eval/agent_matchers.py` and `lab/eval/matchers.py` and
follows the same explicit-mapping shape — roughly 12 matchers covered by ~24
deterministic matcher tests.

**Rationale**: at our scale the indirection costs more than it saves. We have
explicit imports, IDE jump-to-definition works on every dispatch site, and there
is no string-based dispatch surface to debug. A registry would add a layer
without buying anything we currently need.

**Revisit criteria — adopt the registry when ANY of these hits**:

1. Dimensions exceed ~20 (current: 8).
2. Third parties want to register dimensions externally without forking.
3. Dimension dispatch becomes JSON-driven (string ID → class lookup needed at runtime).

**Prep work to keep registry-friendly**:

- Avoid `globals().get(name)` patterns.
- Keep imports explicit.
- Preserve a single central `name → module` mapping (currently `DIMENSION_MODULES` in `lab/eval/scorer.py`).
- When adding a new dimension, add it to that dict — do not introduce a side-channel.
