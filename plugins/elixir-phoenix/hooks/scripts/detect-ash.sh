#!/usr/bin/env bash
# SessionStart hook: Detect Ash Framework and check usage_rules configuration
if { [ -f "mix.exs" ] && grep -q ':ash,' mix.exs 2>/dev/null; } || grep -rq 'use Ash\.Resource\|use Ash\.Domain' lib/ 2>/dev/null; then
  echo "✓ Ash Framework detected — ash-framework skill auto-loads on Ash file edits"
  echo "  Iron Laws: domain code interfaces, actor on query, generators first, codegen after changes"
  echo "  Generators: mix ash.gen.resource | mix ash.gen.domain (use --yes)"
  echo "  Migrations: mix ash.codegen <name> && mix ash.migrate  (NOT hand-edit; NOT mix ecto.migrate)"

  # Check if usage_rules is installed and configured for version-accurate Ash docs
  HAS_DEP=$(grep -c ':usage_rules' mix.exs 2>/dev/null); HAS_DEP=${HAS_DEP:-0}
  HAS_CONFIG=$(grep -c 'usage_rules:' mix.exs 2>/dev/null); HAS_CONFIG=${HAS_CONFIG:-0}

  if [ "$HAS_DEP" -eq 0 ] || [ "$HAS_CONFIG" -eq 0 ]; then
    echo ""
    echo "⚠ usage_rules not configured — Ash docs may not match your installed versions."
    echo "  usage_rules generates live docs from your installed ash_* deps."
    echo "  Install: mix igniter.install usage_rules"
    echo "  Sync:    mix usage_rules.sync"
    echo "  Docs:    https://hexdocs.pm/usage_rules"
  else
    echo "  Research: mix usage_rules.search_docs \"<topic>\" -p ash -p ash_phoenix -p ash_postgres"
  fi
fi
