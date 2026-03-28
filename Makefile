.PHONY: help lint lint-fix eval eval-all eval-fix eval-full eval-ci eval-triggers eval-skills eval-agents eval-est eval-neighbors eval-ablation eval-consistency test ci clean

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

eval-skills: ## Score all skills only
	@bash lab/eval/run_eval.sh --skills

eval-agents: ## Score all agents only
	@bash lab/eval/run_eval.sh --agents

eval-est: ## Evaluator stress test (find gameable matchers)
	@bash lab/eval/run_eval.sh --est

eval-neighbors: ## Neighbor regression (changed skills + confusable neighbors)
	@bash lab/eval/run_eval.sh --neighbors

eval-ablation: ## Matcher ablation (find noise matchers)
	@bash lab/eval/run_eval.sh --ablation

eval-consistency: ## Router consistency test (haiku 5x per prompt)
	@bash lab/eval/run_eval.sh --consistency

# --- Test ---

test: ## Run pytest (52 tests for eval framework)
	@python3 -m pytest lab/eval/tests/ -v --tb=short

test-quick: ## Run pytest (no verbose, fast)
	@python3 -m pytest lab/eval/tests/ -q

# --- CI (full pipeline) ---

ci: lint test eval-all ## Full CI: lint + test + eval (same as GitHub Actions)

# --- Clean ---

clean: ## Remove Python cache files
	@find lab/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find lab/ -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned"
