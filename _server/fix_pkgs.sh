#!/usr/bin/env bash
# fix_pkgs.sh -- install the two packages the first env pass missed.
#
# The setup log recorded "WARN: extras partially failed" for lifelines and shap.
# Re-run them alone so the failure is attributable: a bulk pip install reports a
# single warning that hides which package actually failed and why.
set -u
PY=/usr/local/miniconda3/envs/cis/bin/python
PIP=/usr/local/miniconda3/envs/cis/bin/pip

echo "=== pip index in use ==="
$PIP config get global.index-url

echo "=== installing lifelines + shap (verbose on failure) ==="
$PIP install lifelines shap 2>&1 | tail -15

echo "=== verify ==="
$PY -c "
import importlib
for m in ('lifelines','shap','pandas','numpy','scipy','statsmodels','networkx','pyarrow',
          'torch','torch_geometric','sklearn','matplotlib','seaborn','duckdb'):
    try:
        mod = importlib.import_module(m)
        print('  OK  %-16s %s' % (m, getattr(mod,'__version__','?')))
    except Exception as e:
        print('  --  %-16s %s: %s' % (m, type(e).__name__, e))
"
echo "FIX_PKGS_DONE"
