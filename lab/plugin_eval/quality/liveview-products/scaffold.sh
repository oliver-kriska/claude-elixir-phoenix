#!/usr/bin/env bash
# Catalog context; the fixture's UserLive queries the DB in mount, and the
# prompt asks to follow its style.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=../_shared/base.sh
source "$(dirname "${BASH_SOURCE[0]}")/../_shared/base.sh"
seed_catalog
commit "Add catalog"
