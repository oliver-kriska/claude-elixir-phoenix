#!/usr/bin/env bash
# Accounts + Catalog app; the feature under plan joins the two.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=../_shared/base.sh
source "$(dirname "${BASH_SOURCE[0]}")/../_shared/base.sh"
seed_catalog
commit "Add catalog"
