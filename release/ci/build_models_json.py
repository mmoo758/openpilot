#!/usr/bin/env python3
"""Build a self-hosted driving_models index: every bundle from sunnypilot's published list,
plus our own. Re-run whenever sunnypilot publishes new models to pick them up.

  ./build_models_json.py -o driving_models_v1.json
"""
import argparse
import json
import sys
import urllib.request

UPSTREAM_URL = "https://raw.githubusercontent.com/sunnypilot/sunnypilot-models/refs/heads/gh-pages/docs/driving_models_v17.json"

# `minimum_selector_version` is an equality check against REQUIRED_JSON_VERSION in
# sunnypilot/models/helpers.py, not a minimum -- a bundle declaring anything else is
# silently dropped from the selector with no error shown.
REQUIRED_SELECTOR_VERSION = 15

# Our bundles live at 1000+ so upstream can keep adding models (68, 69, ...) without ever
# colliding on a re-sync. `index` is selection identity -- the manager resolves a download
# with `next(m for m in models if m.index == i)` -- so a collision downloads the wrong model.
# It also sorts them to the top of the selector, which orders by index descending.
CUSTOM_INDEX_BASE = 1000

CUSTOM_BUNDLES = [
  {
    "short_name": "DT",
    "display_name": "Deep RL Test (June 03, 2026)",
    "is_20hz": True,
    "ref": "f02d134f40f5e7be22b182af21b438915a47600e",
    "environment": "development",
    "runner": "tinygrad",
    "minimum_selector_version": str(REQUIRED_SELECTOR_VERSION),
    "generation": "12",
    "build_time": "2026-06-20T09:59:23Z",
    "overrides": {"folder": "RL Models", "lat": ".0", "long": ".3"},
    "models": [
      {
        "type": "supercombo",
        "artifact": {
          "file_name": "driving_dt_tinygrad.pkl",
          "download_uri": {
            "url": "https://cdn.amyjeanes.com/sunnypilot/deep-test-2026-06-03/driving_dt_tinygrad.pkl",
            "sha256": "882c7ce850239901554b8e4fd6dc4838c476cddc90d664a8d65e42b468687778",
          },
        },
      }
    ],
  },
]


def main() -> int:
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument("-o", "--output", required=True, help="path to write the merged index to")
  ap.add_argument("--upstream-url", default=UPSTREAM_URL)
  args = ap.parse_args()

  with urllib.request.urlopen(args.upstream_url, timeout=30) as r:
    upstream = json.load(r)

  bundles = list(upstream.get("bundles", []))
  print(f"upstream: {len(bundles)} bundle(s), max index {max(int(b['index']) for b in bundles)}")

  for offset, bundle in enumerate(CUSTOM_BUNDLES):
    bundle = {**bundle, "index": CUSTOM_INDEX_BASE + offset}
    bundles.append(bundle)
    print(f"  + index {bundle['index']}: {bundle['display_name']}")

  # A duplicate index silently shadows a model, so fail loudly rather than ship one.
  seen: dict[int, str] = {}
  for b in bundles:
    idx = int(b["index"])
    if idx in seen:
      print(f"ERROR: duplicate index {idx}: {seen[idx]!r} and {b['display_name']!r}", file=sys.stderr)
      return 1
    seen[idx] = b["display_name"]

  incompatible = [b["display_name"] for b in bundles
                  if int(b["minimum_selector_version"]) != REQUIRED_SELECTOR_VERSION]
  if incompatible:
    print(f"WARNING: {len(incompatible)} bundle(s) declare minimum_selector_version != "
          + f"{REQUIRED_SELECTOR_VERSION} and will be filtered out of the selector: {incompatible}", file=sys.stderr)

  merged = {"tinygrad_ref": upstream.get("tinygrad_ref"), "bundles": bundles}
  with open(args.output, "w") as f:
    json.dump(merged, f, indent=2)
    f.write("\n")

  print(f"wrote {args.output}: {len(bundles)} bundle(s), {len(bundles) - len(incompatible)} selectable")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
