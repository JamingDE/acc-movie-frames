#!/usr/bin/env python3
"""Builds vid_2.1.0.json - the ACC Cinema graph, GitHub-URL edition (no audio).

Same 12-slot menu state machine as 2.0.0, but:
  - frames + menu texture load from GitHub raw URLs (no resource pack needed);
    URLs are built arithmetically: prefix + str(Frame) + ".jpg" (unpadded names!)
  - playback = the proven vid_1.1.1 recipe: event_periodic period 3 = 6.67 fps
  - WIDGET DESIGN SPACE IS 1536x864 (== surface px). The renderer scales every
    element by surfacePx / WidgetWidth x WidgetHeight, so with the old 140x72
    space pixel-sized elements blew up ~11x (the "fullscreen Template button" bug).
  - buttons bind W/H -> widget ports width/height; two data_branch nodes collapse
    them to 0x0 while a movie plays (hidden from render AND click hit-test).

Reads url_slots.json. Usage: python3 build_cinema_url_graph.py [--version N]
"""
import argparse
import copy
import datetime
import json
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = "/run/media/Phantom/CRYPT/moddingfolder/Instances/All of Create - Aeronautics (1)/shared_graphs"
DOWNLOADS_VID = "/home/Phantom/Downloads/vid.json"

SURF_W, SURF_H = 1536, 864   # widget design space == display surface pixels
CELL_W, CELL_H, COLS = SURF_W // 4, SURF_H // 3, 4


def num(v):
    return {"Payload": {"Value": float(v)}, "Type": "number"}


def string(v):
    return {"Payload": {"Value": v}, "Type": "string"}


class G:
    def __init__(self):
        self.nodes, self.edges = [], []

    def node(self, ntype, x, y, data=None, label=""):
        n = {"Id": str(uuid.uuid4()), "Type": ntype, "X": x, "Y": y,
             "Data": data if data is not None else {}, "Label": label}
        self.nodes.append(n)
        return n["Id"]

    def edge(self, frm, fport, to, tport):
        self.edges.append({"Id": str(uuid.uuid4()), "ToNode": to, "ToPort": tport,
                           "FromNode": frm, "FromPort": fport})


def var_set(name):
    return {"DynamicOutputs": {"value": "number"},
            "PersistentPorts": {"input:exec": 1},
            "DynamicInputs": {"default": "number", "value": "number"},
            "Defaults": {"default": num(0), "exec": num(0), "type": string(name)}}


def build(period):
    cfg = json.load(open(os.path.join(HERE, "url_slots.json")))
    slots = cfg["slots"]
    menu = cfg["menu"]
    enabled = [s for s in slots if s["enabled"] and s["frames"] > 0]

    len_table = "#".join(["0"] + [str(s["frames"]) if s["enabled"] else "0" for s in slots])
    pfx_table = "#".join(["x"] + [s["prefix"] or "x" for s in slots])

    g = G()
    Y = 120

    # ---- clock: 6.67 fps, only advances while playing ----
    tick = g.node("event_periodic", -1500, Y,
                  {"Period": period, "Defaults": {"period": num(period)}})
    br_playing = g.node("branch", -1280, Y)
    br_end = g.node("branch", -1060, Y)
    g.edge(tick, "exec", br_playing, "exec")

    const_zero = g.node("constant_number", -1500, Y + 660, {"Value": 0.0})
    const_one = g.node("constant_number", -1320, Y + 660, {"Value": 1.0})

    end_movie0 = g.node("variable_set", -840, Y, var_set("Movie"))
    end_frame0 = g.node("variable_set", -620, Y, var_set("Frame"))
    start_frame1 = g.node("variable_set", -620, Y + 560, var_set("Frame"))
    tick_frame = g.node("variable_set", -840, Y + 560, var_set("Frame"))

    g.edge(br_playing, "true", br_end, "exec")
    g.edge(br_end, "true", end_movie0, "exec")
    g.edge(end_movie0, "exec", end_frame0, "exec")
    g.edge(br_end, "false", tick_frame, "exec")
    g.edge(const_zero, "value", end_movie0, "value")
    g.edge(const_zero, "value", end_frame0, "value")
    g.edge(const_one, "value", start_frame1, "value")

    # ---- data: counters ----
    movie_v = g.node("variable_get", -1280, Y + 240, {"DynamicOutputs": {"value": "number"}, "Variable": "Movie"})
    frame_v = g.node("variable_get", -1060, Y + 240, {"DynamicOutputs": {"value": "number"}, "Variable": "Frame"})
    add_one = g.node("add", -840, Y + 240, {"Defaults": {"b": num(1)}})
    g.edge(frame_v, "value", add_one, "a")
    g.edge(add_one, "value", tick_frame, "value")

    # ---- tables (index 0 = dummy for menu) ----
    y_t = Y + 400
    len_table_n = g.node("constant_string", -1900, y_t, {"Value": len_table})
    pfx_table_n = g.node("constant_string", -1900, y_t + 220, {"Value": pfx_table})

    def parse_node(x, y):
        return g.node("str_parse_array", x, y,
                      {"Defaults": {"In": string(""), "Delimiter": string("#")}})

    len_parse = parse_node(-1680, y_t)
    pfx_parse = parse_node(-1680, y_t + 220)
    g.edge(len_table_n, "value", len_parse, "In")
    g.edge(pfx_table_n, "value", pfx_parse, "In")

    len_sel = g.node("list_get", -1460, y_t, {"Defaults": {"index": num(0)}})
    pfx_sel = g.node("list_get", -1460, y_t + 220, {"Defaults": {"index": num(0)}})
    g.edge(len_parse, "Array", len_sel, "list")
    g.edge(pfx_parse, "Array", pfx_sel, "list")
    g.edge(movie_v, "value", len_sel, "index")
    g.edge(movie_v, "value", pfx_sel, "index")

    len_num = g.node("convert_type", -1240, y_t, {"OutputType": "number"})
    g.edge(len_sel, "value", len_num, "value")

    # ---- URL = prefix + str(Frame) + ".jpg" ----
    frame_str = g.node("convert_type", -1240, y_t + 220, {"OutputType": "string"})
    g.edge(frame_v, "value", frame_str, "value")
    cat_one = g.node("string_concat", -1020, y_t + 220,
                     {"Defaults": {"a": string(""), "b": string("")}})
    g.edge(pfx_sel, "value", cat_one, "a")
    g.edge(frame_str, "value", cat_one, "b")
    cat_two = g.node("string_concat", -800, y_t + 220,
                     {"Defaults": {"a": string(""), "b": string(".jpg")}})
    g.edge(cat_one, "value", cat_two, "a")

    # ---- logic ----
    playing_cmp = g.node("compare", -1060, Y + 120,
                         {"Defaults": {"b": num(0), "operator": string(">")}})
    ending_cmp = g.node("compare", -840, Y + 120,
                        {"Defaults": {"operator": string(">")}})
    g.edge(movie_v, "value", playing_cmp, "a")
    g.edge(add_one, "value", ending_cmp, "a")
    g.edge(len_num, "value", ending_cmp, "b")
    g.edge(playing_cmp, "value", br_playing, "condition")
    g.edge(ending_cmp, "value", br_end, "condition")

    menu_tex = g.node("constant_string", -800, y_t + 420, {"Value": menu})
    show_branch = g.node("data_branch", -580, y_t + 220,
                         {"Defaults": {"true": string(""), "false": string("")}})
    g.edge(playing_cmp, "value", show_branch, "condition")
    g.edge(cat_two, "value", show_branch, "true")
    g.edge(menu_tex, "value", show_branch, "false")

    at_menu = g.node("not", -1060, Y + 700, {})
    g.edge(playing_cmp, "value", at_menu, "value")
    btn_w = g.node("data_branch", -840, Y + 700,
                   {"Defaults": {"true": num(CELL_W), "false": num(0)}})
    btn_h = g.node("data_branch", -840, Y + 820,
                   {"Defaults": {"true": num(CELL_H), "false": num(0)}})
    g.edge(at_menu, "value", btn_w, "condition")
    g.edge(at_menu, "value", btn_h, "condition")

    # ---- widget: design space == surface px ----
    image_bindings = {k: v for k, v in json.load(open("/tmp/gng/widget_bindings.json")).items()
                      if k not in ("W", "H", "X", "Y")}
    image_el = {"FontSize": 16, "ManagedWidget": 1, "Scale": 1.0, "Rotation": 0.0, "Italic": 0,
                "X": 0, "Visible": 1, "W": SURF_W, "Text": "Widget", "H": SURF_H,
                "Color": -1509377, "FontStyle": "regular", "Y": 0, "Bold": 0,
                "Port": "image", "Texture": menu, "PropertyBindings": image_bindings,
                "Type": "image"}

    elements, dyn_out, ports, pick_by_slot = [image_el], {}, [], {}
    for s in enabled:
        idx = slots.index(s) + 1
        col, row = (idx - 1) % COLS, (idx - 1) // COLS
        port = f"pick{idx}"
        elements.append({
            "FontSize": 44, "ManagedWidget": 1, "Scale": 1.0, "Rotation": 0.0, "Italic": 0,
            "X": col * CELL_W, "Visible": 1, "W": CELL_W, "Text": "PLAY", "H": CELL_H,
            "Color": -1, "FontStyle": "regular", "Y": row * CELL_H, "Bold": 1,
            "BackgroundColor": 0x59000000, "BorderRadius": 12, "BorderWidth": 0,
            "BorderColor": 0x59000000, "InteractionId": str(uuid.uuid4()), "ExecPort": port,
            "PropertyBindings": {"W": "width", "H": "height"}, "Type": "button"})
        dyn_out[port] = "exec"
        ports.append(port)
        pick_by_slot[idx] = port

    defaults = json.load(open("/tmp/gng/widget_defaults.json"))
    defaults["width"] = num(CELL_W)
    defaults["height"] = num(CELL_H)
    defaults["image"] = string(menu)

    widget = g.node("acc_display_widget", 200, Y + 200, {
        "WidgetElements": elements,
        "DynamicInputs": {"image": "string", "width": "number", "height": "number"},
        "DynamicOutputs": dyn_out,
        "HudInteractionPorts": ports,
        "HudFieldLabels": {"image": "image", "width": "W", "height": "H"},
        "Defaults": defaults,
        "WidgetType": "image", "Label": "ACC Display",
        "WidgetWidth": SURF_W, "WidgetHeight": SURF_H})
    g.edge(show_branch, "value", widget, "image")
    g.edge(btn_w, "value", widget, "width")
    g.edge(btn_h, "value", widget, "height")

    # ---- button chains ----
    for i, s in enumerate(enabled):
        idx = slots.index(s) + 1
        x = -1500 + (i % 6) * 300
        y = Y + 980 + (i // 6) * 260
        const_i = g.node("constant_number", x - 140, y, {"Value": float(idx)})
        set_movie = g.node("variable_set", x + 80, y, var_set("Movie"))
        g.edge(widget, pick_by_slot[idx], set_movie, "exec")
        g.edge(const_i, "value", set_movie, "value")
        g.edge(set_movie, "exec", start_frame1, "exec")

    graph = {"Variables": {"Movie": num(0), "Frame": num(0)},
             "ViewportZoom": 0.25, "Revision": 1, "ViewportY": 200.0, "ViewportX": 1600.0,
             "Nodes": g.nodes, "Edges": g.edges, "Functions": [], "Groups": [],
             "Name": "cinema", "Version": 9}
    sg = {"GraphId": str(uuid.uuid4()), "Graph": graph}
    return {"schemaVersion": 1, "kind": "contraption_network_linker",
            "linkerManifestId": None, "linkerId": "",
            "storedGraphs": [copy.deepcopy(sg)],
            "linkerData": {"StoredGraphs": [sg], "SelectedGraphId": sg["GraphId"]},
            "updatedAtGameTime": 0,
            "updatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "displayName": None, "revision": 1}


def validate(doc):
    g = doc["storedGraphs"][0]["Graph"]
    nodes, edges = g["Nodes"], g["Edges"]
    ids = {n["Id"] for n in nodes}
    assert len(ids) == len(nodes)
    assert len(edges) <= 512 and len(nodes) <= 512
    seen = set()
    for e in edges:
        assert e["FromNode"] in ids and e["ToNode"] in ids
        key = (e["FromNode"], e["FromPort"], e["ToNode"], e["ToPort"])
        assert key not in seen, f"duplicate edge {key}"
        seen.add(key)
    for t in [n for n in nodes if n["Type"] == "constant_string"]:
        v = t["Data"]["Value"]
        assert len(v) < 30000
        if v.count("#"):
            assert v.count("#") == 12, "table needs 13 entries"
            for part in v.split("#"):
                if part.startswith("http"):
                    assert len(part) < 2000 and part.endswith(("/", "g_", "f_", "jpg")), part
    js = json.dumps(doc)
    assert len(js) < 250_000
    print(f"nodes={len(nodes)} edges={len(edges)} json={len(js)/1024:.1f} KiB -> OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2.1.0")
    args = ap.parse_args()
    doc = build(json.load(open(os.path.join(HERE, "url_slots.json")))["period"])
    doc["linkerManifestId"] = f"vid_{args.version}"
    doc["displayName"] = f"vid_{args.version}"
    validate(doc)
    for p in (os.path.join(SHARED, f"vid_{args.version}.json"),
              os.path.join(SHARED, "vid.json"), os.path.join(SHARED, "vid_2.json"),
              DOWNLOADS_VID):
        json.dump(doc, open(p, "w"), indent=1)
        print("wrote", p)


if __name__ == "__main__":
    main()
