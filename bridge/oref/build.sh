#!/usr/bin/env bash
# Gather the shipped oref0 SMB decision code into a directory the bridge can require.
#
# Nothing here is written by this project. `determine-basal.js` and `basal-set-temp.js` are
# copied from the AndroidAPS working tree, where they are the reference implementation the
# Kotlin `DetermineBasalSMB` is tested against, so they are the algorithm behind the field
# data this package compares itself with. `round-basal.js` sits one directory above them in
# oref0 and is absent from the AndroidAPS assets, so it comes from an oref0 checkout.
#
# The gathered copy is not committed. It is someone else's source and it belongs in their
# repository, not in this one.
set -euo pipefail
cd "$(dirname "$0")"

OREF_SRC="${OREF_SRC:-$HOME/StudioProjects/Boost-V6/app/src/androidTest/assets/OpenAPSSMB}"
OREF_LIB="${OREF_LIB:-$HOME/StudioProjects/Trio/trio-oref/lib}"

for f in determine-basal.js basal-set-temp.js; do
    [ -f "$OREF_SRC/$f" ] || { echo "no $f under $OREF_SRC; set OREF_SRC" >&2; exit 1; }
done
[ -f "$OREF_LIB/round-basal.js" ] || { echo "no round-basal.js under $OREF_LIB; set OREF_LIB" >&2; exit 1; }

rm -rf vendor && mkdir -p vendor/oref vendor/node_modules/lodash
cp "$OREF_SRC/determine-basal.js" "$OREF_SRC/basal-set-temp.js" vendor/oref/
# determine-basal requires it as ../round-basal and basal-set-temp as ./round-basal, so it
# has to sit in both places.
cp "$OREF_LIB/round-basal.js" vendor/
cp "$OREF_LIB/round-basal.js" vendor/oref/

# `round-basal` reaches for lodash to ask whether a Medtronic model string ends in 23 or 54,
# which selects a finer basal increment. That is a string test rather than anything about
# insulin, so it is answered with the built-in instead of pulling in the library. The pumps
# this package simulates carry no model string, so the branch it guards is never taken; the
# shim exists to satisfy the import.
cat > vendor/node_modules/lodash/endsWith.js <<'JS'
module.exports = (s, t) => String(s).endsWith(t)
JS
echo '{"name":"lodash","version":"0.0.0-shim","main":"endsWith.js"}' > vendor/node_modules/lodash/package.json

echo "gathered:"
ls -1 vendor/oref vendor/round-basal.js
