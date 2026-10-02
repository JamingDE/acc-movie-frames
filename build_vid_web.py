#!/usr/bin/env python3
"""vid 1.1.x (web edition) - ACC movie graph streaming frames from a URL.

The display client downloads http(s) images itself, so the graph stays
tiny (no 512 KiB problem) and frames can be high resolution. Constraints
(verified in G&G bytecode): https + public host only, <=2 MiB/image,
<=4096px, client cache <=64 textures / 33.5M pixels (this build:
60 x 960x540 = 31.1M px - no eviction after first loop).

Usage:
  python3 build_vid_web.py [--base <url-prefix>]
Default base points at the JamingDE/acc-movie-frames GitHub repo.
"""
import json, uuid, os, datetime, argparse, glob

PERIOD_TICKS_FROM_ARGS = True  # period comes from --period
NAMESP = uuid.uuid5(uuid.NAMESPACE_URL, "acc-vid-web")
SURF_W, SURF_H = 1536, 864
GRAPH_ID = "e2d303bc-5e06-38bf-b27f-a0628eba1bd8"
SG = "/run/media/Phantom/CRYPT/moddingfolder/Instances/All of Create - Aeronautics (1)/shared_graphs"

DEFAULT_BASE = "https://raw.githubusercontent.com/JamingDE/acc-movie-frames/main/frames"

ap = argparse.ArgumentParser()
ap.add_argument("--base", default=DEFAULT_BASE)
ap.add_argument("--version", default="1.1.0")
ap.add_argument("--frames", type=int, default=60)
ap.add_argument("--pattern", default="f_%02d")
ap.add_argument("--period", type=int, default=10)
args = ap.parse_args()

def u(name): return str(uuid.uuid5(NAMESP, args.version + "/" + name))
def num(v):  return {"Payload": {"Value": float(v)}, "Type": "number"}
def stri(v): return {"Payload": {"Value": v}, "Type": "string"}

base = args.base.rstrip("/")
urls = [f"{base}/{args.pattern % i}.jpg" for i in range(1, args.frames + 1)]
N = len(urls)
assert all(len(x) < 2048 for x in urls), "URLs must stay under 2048 chars"
frame_table = "#".join(urls)
assert len(frame_table) < 30000
poster = urls[0]

widget_defaults = json.load(open("/tmp/gng/widget_defaults.json"))
bindings = json.load(open("/tmp/gng/widget_bindings.json"))
widget_defaults.update({
    "x": num(0), "y": num(0), "width": num(SURF_W), "height": num(SURF_H),
    "scale": num(1), "rotation": num(0), "font_size": num(16),
    "label": stri("Movie"),
    "visible": {"Payload": {"Value": 1.0}, "Type": "number"},
    "image": stri(poster),
})
image_el = {
    "FontSize": 16, "ManagedWidget": 1, "Scale": 1.0, "Rotation": 0.0,
    "Italic": 0, "X": 0, "Visible": 1, "W": SURF_W, "Text": "Widget",
    "H": SURF_H, "Color": -1509377, "FontStyle": "regular", "Y": 0,
    "Bold": 0, "Port": "image",
    "PropertyBindings": bindings, "Type": "image", "Texture": poster,
}

var_set_frame = {
    "DynamicOutputs": {"value": "number"},
    "PersistentPorts": {"input:exec": 1},
    "DynamicInputs": {"default": "number", "value": "number"},
    "Defaults": {"default": num(0), "exec": num(0), "type": stri("integer")},
    "VariableType": "integer", "VariableDefinition": 1,
    "RegisteredVariable": "Frame",
    "PersistentPortValues": {"input:exec": num(0)},
    "InputOptions": {"type": ["boolean", "integer", "float", "string",
                              "direction", "frequency", "target", "list", "map"]},
    "EditorCollapsed": 1, "Variable": "Frame",
}

nodes = [
    {"Y": 20, "X": -1150, "Id": u("periodic"), "Type": "event_periodic",
     "Data": {"Period": args.period,
              "PersistentPortValues": {"output:exec": num(0)},
              "Defaults": {"period": num(args.period)},
              "PersistentPorts": {"output:exec": 1}}},
    {"Y": -320, "X": -1150, "Id": u("one"), "Label": "1", "Type": "constant_number",
     "Data": {"Value": 1.0}},
    {"Y": 20, "X": -680, "Id": u("setframe"), "Label": "Frame++", "Type": "variable_set",
     "Data": var_set_frame},
    {"Y": -120, "X": -680, "Id": u("getf1"), "Label": "Frame", "Type": "variable_get",
     "Data": {"DynamicOutputs": {"value": "number"}, "Variable": "Frame"}},
    {"Y": -220, "X": -680, "Id": u("add"), "Label": "+1", "Type": "add",
     "Data": {"Defaults": {"b": num(1)}}},
    {"Y": -220, "X": -460, "Id": u("mod"), "Label": "% N", "Type": "modulo", "Data": {}},
    {"Y": -320, "X": -460, "Id": u("nframes"), "Label": "frames", "Type": "constant_number",
     "Data": {"Value": float(N)}},
    {"Y": 120, "X": -680, "Id": u("getf2"), "Label": "Frame", "Type": "variable_get",
     "Data": {"DynamicOutputs": {"value": "number"}, "Variable": "Frame"}},
    {"Y": 260, "X": -900, "Id": u("table"), "Label": "frame URLs", "Type": "constant_string",
     "Data": {"Value": frame_table}},
    {"Y": 360, "X": -900, "Id": u("delim"), "Label": "delim", "Type": "constant_string",
     "Data": {"Value": "#"}},
    {"Y": 300, "X": -620, "Id": u("split"), "Label": "split", "Type": "str_parse_array",
     "Data": {"Defaults": {"In": stri(""), "Delimiter": stri("#")}}},
    {"Y": 120, "X": -340, "Id": u("lget"), "Label": "frame url", "Type": "list_get",
     "Data": {"Defaults": {"index": num(0)}}},
    {"Y": 20, "X": 300, "Id": u("widget"), "Label": "ACC Display",
     "Type": "acc_display_widget",
     "Data": {"WidgetElements": [image_el],
              "DynamicInputs": {"image": "string", "value": "any"},
              "Defaults": widget_defaults,
              "WidgetWidth": 140, "WidgetType": "image", "WidgetHeight": 72,
              "HudFieldLabels": {"image": "image", "value": "Value"}}},
]

key = {k: u(k) for k in
       ["periodic", "one", "setframe", "getf1", "add", "mod", "nframes",
        "getf2", "table", "delim", "split", "lget", "widget"]}

def E(a, ap, b, bp):
    return {"Id": u("e-" + a[-6:] + ap + "-" + b[-6:] + bp),
            "ToNode": b, "ToPort": bp, "FromNode": a, "FromPort": ap}

edges = [
    E(key["periodic"], "exec", key["setframe"], "exec"),
    E(key["getf1"], "value", key["add"], "a"),
    E(key["one"], "value", key["add"], "b"),
    E(key["add"], "value", key["mod"], "a"),
    E(key["nframes"], "value", key["mod"], "b"),
    E(key["mod"], "value", key["setframe"], "value"),
    E(key["getf2"], "value", key["lget"], "index"),
    E(key["table"], "value", key["split"], "In"),
    E(key["delim"], "value", key["split"], "Delimiter"),
    E(key["split"], "Array", key["lget"], "list"),
    E(key["lget"], "value", key["widget"], "image"),
]

graph = {
    "Variables": {"Frame": {"Payload": {"Value": 0.0}, "Type": "number"}},
    "ViewportZoom": 0.25, "Revision": 78, "ViewportY": 200.0,
    "Nodes": nodes, "Edges": edges,
    "Functions": [], "Groups": [], "ViewportX": 100.0, "Version": 9,
    "Name": "vid",
}

def manifest_for(mid):
    stored = {"GraphId": GRAPH_ID, "Graph": json.loads(json.dumps(graph))}
    return {
        "schemaVersion": 1, "kind": "contraption_network_linker",
        "linkerManifestId": mid, "linkerId": "",
        "storedGraphs": [stored],
        "linkerData": {"StoredGraphs": [json.loads(json.dumps(stored))],
                       "SelectedGraphId": GRAPH_ID},
        "updatedAtGameTime": 0,
        "updatedAt": datetime.datetime.now(datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "displayName": mid, "revision": 1,
    }

for fname, mid in [(f"vid_{args.version}.json", f"vid_{args.version}"),
                   ("vid.json", "vid"), ("vid_2.json", "vid_2")]:
    with open(os.path.join(SG, fname), "w") as fh:
        json.dump(manifest_for(mid), fh, separators=(",", ":"), ensure_ascii=False)
    print("wrote", os.path.join(SG, fname))
with open("/home/Phantom/Downloads/vid.json", "w") as fh:
    json.dump(manifest_for(f"vid_{args.version}"), fh, separators=(",", ":"), ensure_ascii=False)
print(f"nodes: {len(nodes)} | edges: {len(edges)} | frames: {N} @ {20/args.period} fps, loop {N/(20/args.period):.1f}s")
print("base:", base)
