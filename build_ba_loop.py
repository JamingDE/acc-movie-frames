#!/usr/bin/env python3
"""vid_1.1.2 = vid_1.1.1 (the proven in-game loop) patched to play the FULL
Bad Apple (1461 frames, 219 s) on loop at 6.67 fps.

Minimal diff against vid_1.1.1.json:
  - frame wrap: Frame = (Frame mod 1461) + 1   (was (Frame+1) mod 64, which
    produced 0..63 for a 0-based URL table; arithmetic URLs need 1..1461)
  - URL: table of padded full URLs (111 KB, over the 32k NBT string limit at
    this length) replaced by prefix + str(Frame) + ".jpg" (ba_ frames are
    UNPADDED on GitHub). str() = convert_type OutputType string, which renders
    integral doubles without ".0" (bytecode-verified).
  - widget element Texture default g_01.jpg -> ba_1.jpg
Everything else (widget, periodic, variable_set) is byte-identical to 1.1.1.
"""
import json

SHARED = "/run/media/Phantom/CRYPT/moddingfolder/Instances/All of Create - Aeronautics (1)/shared_graphs"
PREFIX = "https://raw.githubusercontent.com/JamingDE/acc-movie-frames/main/frames/ba_"
FRAMES = 1461

d = json.load(open(f"{SHARED}/vid_1.1.1.json"))
g = d["storedGraphs"][0]["Graph"]


def num(v):
    return {"Payload": {"Value": float(v)}, "Type": "number"}


def string(v):
    return {"Payload": {"Value": v}, "Type": "string"}


keep = {}
for n in g["Nodes"]:
    keep[n["Type"] + ("@" + n["Data"]["Variable"] if n["Type"] == "variable_get" else "")] = n

tick = keep["event_periodic"]
const_one = keep["constant_number"]          # 1.0 (only one besides the 64)
var_set = keep["variable_set"]
frame_mod = keep["variable_get@Frame"]       # first var_get (modulo path)
add = keep["add"]
mod = keep["modulo"]
const_n = keep["constant_number"]            # dup key overwritten; rebuild below
widget = keep["acc_display_widget"]

# the two constant_numbers are ambiguous by type; split by value
consts = [n for n in g["Nodes"] if n["Type"] == "constant_number"]
const_one = next(n for n in consts if n["Data"]["Value"] == 1.0)
const_n = next(n for n in consts if n["Data"]["Value"] == 64.0)
const_n["Data"]["Value"] = float(FRAMES)

frame_url = keep.get("variable_get@Frame")   # need a SECOND var_get; clone instead
frame_url = json.loads(json.dumps(frame_mod))
frame_url["X"], frame_url["Y"] = -680, 260

prefix_n = next(n for n in g["Nodes"] if n["Type"] == "constant_string"
                and n["Data"]["Value"].startswith("http"))
prefix_n["Data"]["Value"] = PREFIX
prefix_n["X"], prefix_n["Y"] = -900, 360

conv = {"Id": prefix_n["Id"], "Type": "convert_type", "X": -620, "Y": 260,
        "Data": {"OutputType": "string"}, "Label": ""}   # new ids below
cat_one = next(n for n in g["Nodes"] if n["Type"] == "str_parse_array")
cat_one.update({"Type": "string_concat", "X": -340, "Y": 260,
                "Data": {"Defaults": {"a": string(""), "b": string("")}}, "Label": ""})
listget = next(n for n in g["Nodes"] if n["Type"] == "list_get")
listget.update({"Type": "string_concat", "X": -80, "Y": 260,
                "Data": {"Defaults": {"a": string(""), "b": string(".jpg")}}, "Label": ""})

import uuid
conv["Id"] = str(uuid.uuid4())
del_keep = None
for n in g["Nodes"]:
    if n["Type"] == "constant_string" and n["Data"]["Value"] == "#":
        del_keep = n
g["Nodes"].remove(del_keep)
g["Nodes"] += [frame_url, conv]

for el in widget["Data"]["WidgetElements"]:
    if el.get("Type") == "image" and "g_01" in str(el.get("Texture", "")):
        el["Texture"] = PREFIX + "1.jpg"

ids = {n["Id"] for n in g["Nodes"]}
g["Edges"] = [e for e in g["Edges"] if e["FromNode"] in ids and e["ToNode"] in ids]

N = {n["Id"]: n for n in g["Nodes"]}
frame_mod_id, add_id, mod_id = frame_mod["Id"], add["Id"], mod["Id"]
g["Edges"] = [
    {"Id": str(uuid.uuid4()), "ToNode": var_set["Id"], "ToPort": "exec",
     "FromNode": tick["Id"], "FromPort": "exec"},
    # Frame' = (Frame mod 1461) + 1
    {"Id": str(uuid.uuid4()), "ToNode": mod_id, "ToPort": "a",
     "FromNode": frame_mod_id, "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": mod_id, "ToPort": "b",
     "FromNode": const_n["Id"], "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": add_id, "ToPort": "a",
     "FromNode": mod_id, "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": add_id, "ToPort": "b",
     "FromNode": const_one["Id"], "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": var_set["Id"], "ToPort": "value",
     "FromNode": add_id, "FromPort": "value"},
    # URL = prefix + str(Frame) + ".jpg"
    {"Id": str(uuid.uuid4()), "ToNode": conv["Id"], "ToPort": "value",
     "FromNode": frame_url["Id"], "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": cat_one["Id"], "ToPort": "a",
     "FromNode": prefix_n["Id"], "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": cat_one["Id"], "ToPort": "b",
     "FromNode": conv["Id"], "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": listget["Id"], "ToPort": "a",
     "FromNode": cat_one["Id"], "FromPort": "value"},
    {"Id": str(uuid.uuid4()), "ToNode": widget["Id"], "ToPort": "image",
     "FromNode": listget["Id"], "FromPort": "value"},
]

d["linkerManifestId"] = "vid_1.1.2"
d["displayName"] = "vid_1.1.2"
sg = d["linkerData"]["StoredGraphs"][0]
sg["Graph"] = g
assert d["storedGraphs"][0]["Graph"] is g

js = json.dumps(d)
assert len(js) < 250_000
print(f"nodes={len(g['Nodes'])} edges={len(g['Edges'])} json={len(js)/1024:.1f} KiB")
for p in (f"{SHARED}/vid_1.1.2.json", f"{SHARED}/vid.json", f"{SHARED}/vid_2.json",
          "/home/Phantom/Downloads/vid.json"):
    json.dump(d, open(p, "w"), indent=1)
    print("wrote", p)
