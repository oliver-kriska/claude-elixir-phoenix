.PHONY: help lint lint-fix eval eval-all eval-fix eval-full eval-ci eval-triggers eval-tournament eval-skills eval-agents eval-multimodel eval-compare-models test validate amp-skills amp-skills-sync amp-skills-validate codex-skills codex-skills-sync codex-skills-validate security ci clean

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

eval-all: ## Score all 50 skills + 25 agents (structural)
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

eval-agents: ## Score all agents only
	@bash lab/eval/run_eval.sh --agents

# --- Test ---

test: ## Run pytest for eval framework and port primitives
	@python3 -m pytest lab/eval/tests/ scripts/tests/ -v --tb=short

test-quick: ## Run pytest (no verbose, fast)
	@python3 -m pytest lab/eval/tests/ scripts/tests/ -q

# --- Validate ---

validate: ## Run claude plugin validate on plugin structure
	@claude plugin validate plugins/elixir-phoenix

amp-skills: ## Generate Amp skills from the canonical Claude plugin
	@python3 -m scripts.build_amp_skills

amp-skills-sync: ## Regenerate and verify the committed Amp target
	@$(MAKE) amp-skills
	@$(MAKE) amp-skills-validate

amp-skills-validate: ## Check committed Amp skills for generated drift
	@python3 -m scripts.build_amp_skills --check

codex-skills: ## Generate the Codex skills plugin from the canonical Claude plugin
	@python3 -m scripts.build_codex_skills

codex-skills-sync: ## Regenerate and verify the committed Codex target
	@$(MAKE) codex-skills
	@$(MAKE) codex-skills-validate

codex-skills-validate: ## Check committed Codex skills for generated drift
	@python3 -m scripts.build_codex_skills --check

# --- Security ---

security: ## SkillSpector scan of all skills + agents (skips if not installed)
	@if command -v skillspector >/dev/null 2>&1; then \
		bash lab/skillspector/scan.sh; \
	else \
		echo "⊘ skillspector not installed — skipping security scan."; \
		echo "  Install: pipx install --python python3.13 \"git+https://github.com/NVIDIA/skillspector.git\""; \
	fi

# --- CI (full pipeline) ---

ci: lint test validate amp-skills-validate codex-skills-validate eval-all security ## Full CI: lint + test + validate + eval + security (same as GitHub Actions)

# --- Clean ---

clean: ## Remove Python cache files
	@find lab/ scripts/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find lab/ scripts/ -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned"
