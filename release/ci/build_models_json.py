#!/usr/bin/env python3
"""Build the self-hosted driving_models index.

Since the tinygrad bump to ef37830d, every pkl sunnypilot publishes fails to load -- they were
compiled against ac1632ab and the serialised JIT graphs are not portable across that gap
(verified on device: unpickling raises AssertionError on Ops.SLICE). So this index cannot merge
upstream's bundle list any more: listing a model we can't run means a user downloads a few
hundred MB and gets a crash.

Instead it emits only models we have recompiled ourselves. Upstream is still fetched, but purely
for bundle *metadata* -- display name, ref, generation, overrides -- so entries stay faithful to
what sunnypilot published; only the artifact URL and hash are rewritten to ours.

To add a model: recompile its ONNX on a comma 3X (see RECOMPILED below for where the ONNX comes
from), upload the pkl, and add an entry here.

  ./build_models_json.py -o driving_models_v1.json
"""
import argparse
import json
import sys
import urllib.request

UPSTREAM_URL = "https://raw.githubusercontent.com/sunnypilot/sunnypilot-models/refs/heads/gh-pages/docs/driving_models_v17.json"
CDN = "https://cdn.amyjeanes.com/sunnypilot"

# `minimum_selector_version` is an equality check against REQUIRED_JSON_VERSION in
# sunnypilot/models/helpers.py, not a minimum -- a bundle declaring anything else is
# silently dropped from the selector with no error shown.
REQUIRED_SELECTOR_VERSION = 15

# Upstream bundles we have recompiled against the current tinygrad, keyed by their short_name.
# Their ONNX comes from the bundle's own `ref` commit in commaai/openpilot, under
# selfdrive/modeld/models/{driving_vision,driving_policy}.onnx via git LFS.
RECOMPILED = {
  "C210M": {
    "file_name": "driving_c210m_tinygrad.pkl",
    "url": f"{CDN}/c210m-recompiled/driving_c210m_tinygrad.pkl",
    "sha256": "6085c969a7a49077596981ec53c49490be2441558fa100fd8260132e8e34d2be",
  },
  "PMV2": {
    "file_name": "driving_pmv2_tinygrad.pkl",
    "url": f"{CDN}/pmv2-recompiled/driving_pmv2_tinygrad.pkl",
    "sha256": "fefcb6c25974700bf618528fda2b1ac6d1c3be0e2a78df698b4234a904d3fe51",
  },
}

# Models with no upstream bundle to inherit from. Index 1000+ so upstream indices can never
# collide -- `index` is selection identity in the manager, not just sort order -- and so they
# sort to the top of the selector, which orders by index descending.
CUSTOM_INDEX_BASE = 1000

CUSTOM_BUNDLES = [
  {
    # commaai/openpilot#38164, merged 2026-07-23 and reverted the next day by #38449.
    # Compiled from the ONNX at that commit; needs tinygrad >= ef37830d to build at all.
    "short_name": "RL",
    "display_name": "Rebel Legion (July 23, 2026)",
    "is_20hz": True,
    "ref": "2895346746634d7eec0ee749f946c87039948a25",
    "environment": "development",
    "runner": "tinygrad",
    "minimum_selector_version": str(REQUIRED_SELECTOR_VERSION),
    "generation": "12",
    # comma shipped this model with LAT_SMOOTH_SECONDS/LONG_SMOOTH_SECONDS both at 0.1
    "overrides": {"folder": "RL Models", "lat": ".1", "long": ".1"},
    "models": [
      {
        "type": "supercombo",
        "artifact": {
          "file_name": "driving_rl_tinygrad.pkl",
          "download_uri": {
            "url": f"{CDN}/rebel-legion-2026-07-23/driving_rl_tinygrad.pkl",
            "sha256": "0ebc267d34033c96d2ae105127e4f08417d590dbe751b088efadf8e6711506ac",
          },
        },
      }
    ],
  },
]


def rehost(bundle: dict, artifact: dict) -> dict:
  """Point every model entry in an upstream bundle at our recompiled pkl. Upstream lists one
  entry per model type (vision, policy, ...) all naming the same combined file, so they all get
  the same artifact."""
  bundle = dict(bundle)
  bundle["models"] = [
    {**m, "artifact": {"file_name": artifact["file_name"],
                       "download_uri": {"url": artifact["url"], "sha256": artifact["sha256"]}}}
    for m in bundle.get("models", [])
  ]
  return bundle


def main() -> int:
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument("-o", "--output", required=True, help="path to write the index to")
  ap.add_argument("--upstream-url", default=UPSTREAM_URL)
  args = ap.parse_args()

  with urllib.request.urlopen(args.upstream_url, timeout=30) as r:
    upstream = json.load(r)

  by_short = {b["short_name"]: b for b in upstream.get("bundles", [])}
  missing = sorted(set(RECOMPILED) - set(by_short))
  if missing:
    print(f"ERROR: no upstream bundle for {missing} -- short_name changed or bundle withdrawn?", file=sys.stderr)
    return 1

  bundles = []
  for short_name, artifact in RECOMPILED.items():
    bundles.append(rehost(by_short[short_name], artifact))
    print(f"  rehosted {by_short[short_name]['index']:>4}: {by_short[short_name]['display_name']}")

  for offset, bundle in enumerate(CUSTOM_BUNDLES):
    bundle = {**bundle, "index": CUSTOM_INDEX_BASE + offset}
    bundles.append(bundle)
    print(f"  custom   {bundle['index']:>4}: {bundle['display_name']}")

  # A duplicate index silently shadows a model, so fail loudly rather than ship one.
  seen: dict[int, str] = {}
  for b in bundles:
    idx = int(b["index"])
    if idx in seen:
      print(f"ERROR: duplicate index {idx}: {seen[idx]!r} and {b['display_name']!r}", file=sys.stderr)
      return 1
    seen[idx] = b["display_name"]

  bad = [b["display_name"] for b in bundles
         if int(b["minimum_selector_version"]) != REQUIRED_SELECTOR_VERSION]
  if bad:
    print(f"ERROR: {len(bad)} bundle(s) declare minimum_selector_version != "
          + f"{REQUIRED_SELECTOR_VERSION} and would be dropped by the selector: {bad}", file=sys.stderr)
    return 1

  merged = {"tinygrad_ref": "ef37830d138838933d6d70d0024de9f130cb2308", "bundles": bundles}
  with open(args.output, "w") as f:
    json.dump(merged, f, indent=2)
    f.write("\n")

  print(f"wrote {args.output}: {len(bundles)} bundle(s)")
  print(f"dropped {len(by_short) - len(RECOMPILED)} upstream bundle(s) not recompiled for this tinygrad")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
