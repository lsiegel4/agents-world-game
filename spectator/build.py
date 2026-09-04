#!/usr/bin/env python3
"""Build the spectator page with the run data embedded."""
import json, os, sys

here = os.path.dirname(os.path.abspath(__file__))
data = open(os.path.join(here, "world.json")).read()
template = open(os.path.join(here, "template.html")).read()
out = template.replace("/*__WORLD_DATA__*/null", data)
path = os.path.join(here, "index.html")
open(path, "w").write(out)
print(f"wrote {path} ({os.path.getsize(path)/1024:.0f} KB)")
