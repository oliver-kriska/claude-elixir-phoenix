.PHONY: help lint lint-fix eval eval-all eval-fix eval-full eval-ci eval-triggers eval-tournament eval-skills eval-agents eval-multimodel eval-compare-models test validate ci clean

# Default target
help: ## Show available commands
	@echo "Plugin Quality Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Lint ---

lint: ## Lint markdown, YAML, JSON
	@npx markdownlint "**/*.md" --ignore node_modules --ignore docs --ignore reports --ignore analysis --ignore scratchpad --ignore lab/findings

lint-fix: ## Auto-fix markdown lint errors
	@npx markdownlint "**/*.md" --fix --ignore node_modules --ignore docs --ignore reports --ignore analysis --ignore scratchpad --ignore lab/findings

# --- Eval ---

eval: ## Quick: lint + score changed skills/agents only
	@bash lab/eval/run_eval.sh --changed

eval-all: ## Score all 40 skills + 20 agents (structural)
	@bash lab/eval/run_eval.sh --all

eval-fix: ## Auto-fix lint + show failures + suggest autoresearch command
	@bash lab/eval/run_eval.sh --fix

eval-full: ## Everything: structural + behavioral triggers (~60 min)
	@bash lab/eval/run_eval.sh --all && bash lab/eval/run_eval.sh --triggers

eval-ci: ## CI gate: lint + all skills + all agents
	@bash lab/eval/run_eval.sh --ci

eval-triggers: ## Re-run behavioral trigger tests (~60 min, uses haiku)
	@bash lab/eval/run_eval.sh --triggers

eval-multimodel: ## Run trigger eval against sonnet (slow, ~$$3, ~3 hr). Override: MODEL=opus make eval-multimodel
	@python3 -m lab.eval.trigger_scorer --all --model $${MODEL:-sonnet}

eval-compare-models: ## Compare per-skill accuracy across models. Override: MODELS=haiku,sonnet,opus make eval-compare-models
	@python3 -m lab.eval.compare_models --models $${MODELS:-haiku,sonnet}

eval-tournament: ## Run tournament on weak skills (<75% trigger accuracy)
	@python3 -m lab.tournament.description_tournament --weak

eval-skills: ## Score all skills only
	@bash lab/eval/run_eval.sh --skills

eval-inspector: ## Score elixir-inspector plugin (skills + agents)
	@echo "=== Inspector Skills ===" && python3 -m lab.eval.scorer --all --plugin elixir-inspector 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); perfect=sum(1 for v in d.values() if v['composite']>=0.999); avg=sum(v['composite'] for v in d.values())/len(d) if d else 0; print(f'  {len(d)} skills | {perfect} perfect | avg {avg:.3f}')"
	@echo "=== Inspector Agents ===" && python3 -m lab.eval.agent_scorer --all --plugin elixir-inspector 2>&1 | tail -1

eval-all-plugins: ## Score ALL plugins (elixir-phoenix + elixir-inspector)
	@echo "=== elixir-phoenix ===" && $(MAKE) eval-all 2>&1 | grep -E "skills|agents"
	@echo "=== elixir-inspector ===" && $(MAKE) eval-inspector 2>&1 | grep -E "skills|agents"

eval-agents: ## Score all agents only
	@bash lab/eval/run_eval.sh --agents

# --- Test ---

test: ## Run pytest (52 tests for eval framework)
	@python3 -m pytest lab/eval/tests/ -v --tb=short

test-quick: ## Run pytest (no verbose, fast)
	@python3 -m pytest lab/eval/tests/ -q

# --- Validate ---

validate: ## Run claude plugin validate on plugin structure
	@claude plugin validate plugins/elixir-phoenix

# --- CI (full pipeline) ---

ci: lint test validate eval-all ## Full CI: lint + test + validate + eval (same as GitHub Actions)

# --- Clean ---

clean: ## Remove Python cache files
	@find lab/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find lab/ -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned"
