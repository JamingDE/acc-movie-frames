#!/usr/bin/env python3
"""Builds vid_2.0.0.json - the ACC Cinema graph.

State machine:
  Movie = 0 -> poster menu wall (12 slots, click an enabled slot's button to start)
  Movie = i -> plays slot i's frames at 20 fps (event_tick), sound via play_sound
  frame N+1 >= length -> back to menu, sound stopped

Frame paths are built arithmetically (prefix + str(N) + ".jpg") via string_concat +
convert_type, so the graph size is INDEPENDENT of movie length.

Reads slots.json (from build_cinema_pack.py). Usage: python3 build_cinema_graph.py
"""
import copy
import datetime
import json
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = "/run/media/Phantom/CRYPT/moddingfolder/Instances/All of Create - Aeronautics (1)/shared_graphs"
TEMPLATE = os.path.join(SHARED, "vid_1.1.1.json")
VERSION = "2.0.0"
DOWNLOADS_VID = "/home/Phantom/Downloads/vid.json"

CELL_W, CELL_H, COLS = 384, 288, 4


def num(v):
    return {"Payload": {"Value": float(v)}, "Type": "number"}


def string(v):
    return {"Payload": {"Value": v}, "Type": "string"}


def boolean(v):
    return {"Payload": {"Value": v}, "Type": "boolean"}


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


def build():
    cfg = json.load(open(os.path.join(HERE, "slots.json")))
    ns = cfg["namespace"]
    menu = cfg["menu"]
    slots = cfg["slots"]  # 12 entries: {id, index, frames, sound, enabled}
    enabled = [s for s in slots if s["enabled"] and s["frames"] > 0]

    # ---- tables (index 0 = dummy for menu state) ----
    len_table = "#".join(["0"] + [str(s["frames"]) if s["enabled"] else "0" for s in slots])
    pfx_table = "#".join(["x"] + [f"{ns}:textures/movie/{s['id']}/" if s["enabled"] else "x" for s in slots])
    snd_table = "#".join(["-"] + [s["sound"] or "-" for s in slots])

    g = G()
    Y = 120

    # ================= EXEC CHAIN =================
    tick = g.node("event_tick", -1500, Y)
    br_playing = g.node("branch", -1280, Y)
    br_end = g.node("branch", -1060, Y)
    g.edge(tick, "exec", br_playing, "exec")

    const_zero = g.node("constant_number", -1280, Y + 620, {"Value": 0.0})

    end_movie0 = g.node("variable_set", -840, Y,
                        {"DynamicOutputs": {"value": "number"},
                         "PersistentPorts": {"input:exec": 1},
                         "DynamicInputs": {"default": "number", "value": "number"},
                         "Defaults": {"default": num(0), "exec": num(0), "type": string("Movie")}})
    end_frame0 = g.node("variable_set", -620, Y,
                        {"DynamicOutputs": {"value": "number"},
                         "PersistentPorts": {"input:exec": 1},
                         "DynamicInputs": {"default": "number", "value": "number"},
                         "Defaults": {"default": num(0), "exec": num(0), "type": string("Frame")}})
    start_frame0 = g.node("variable_set", -620, Y + 560,
                          {"DynamicOutputs": {"value": "number"},
                           "PersistentPorts": {"input:exec": 1},
                           "DynamicInputs": {"default": "number", "value": "number"},
                           "Defaults": {"default": num(0), "exec": num(0), "type": string("Frame")}})
    tick_frame = g.node("variable_set", -840, Y + 560,
                        {"DynamicOutputs": {"value": "number"},
                         "PersistentPorts": {"input:exec": 1},
                         "DynamicInputs": {"default": "number", "value": "number"},
                         "Defaults": {"default": num(0), "exec": num(0), "type": string("Frame")}})

    play_snd = g.node("play_sound", -400, Y + 560,
                      {"Defaults": {"sound": string(""), "world": boolean(False),
                                    "x": num(0), "y": num(0), "z": num(0),
                                    "volume": num(4), "pitch": num(1),
                                    "loop": boolean(False)}})

    g.edge(br_playing, "true", br_end, "exec")
    g.edge(br_end, "true", end_movie0, "exec")
    g.edge(end_movie0, "exec", end_frame0, "exec")
    g.edge(end_frame0, "exec", play_snd, "stop")
    g.edge(br_end, "false", tick_frame, "exec")
    g.edge(start_frame0, "exec", play_snd, "exec")
    g.edge(const_zero, "value", end_movie0, "value")
    g.edge(const_zero, "value", end_frame0, "value")
    g.edge(const_zero, "value", start_frame0, "value")

    # ================= VARIABLES / MATH =================
    movie_v = g.node("variable_get", -1280, Y + 240, {"DynamicOutputs": {"value": "number"}, "Variable": "Movie"})
    frame_v = g.node("variable_get", -1060, Y + 240, {"DynamicOutputs": {"value": "number"}, "Variable": "Frame"})
    add_one = g.node("add", -840, Y + 240, {"Defaults": {"b": num(1)}})
    g.edge(frame_v, "value", add_one, "a")
    g.edge(add_one, "value", tick_frame, "value")

    # ================= TABLES =================
    y_t = Y + 400
    len_table_n = g.node("constant_string", -1900, y_t, {"Value": len_table})
    pfx_table_n = g.node("constant_string", -1900, y_t + 220, {"Value": pfx_table})
    snd_table_n = g.node("constant_string", -1900, y_t + 440, {"Value": snd_table})

    def parse_node(x, y):
        return g.node("str_parse_array", x, y,
                      {"Defaults": {"In": string(""), "Delimiter": string("#")}})

    len_parse = parse_node(-1680, y_t)
    pfx_parse = parse_node(-1680, y_t + 220)
    snd_parse = parse_node(-1680, y_t + 440)
    g.edge(len_table_n, "value", len_parse, "In")
    g.edge(pfx_table_n, "value", pfx_parse, "In")
    g.edge(snd_table_n, "value", snd_parse, "In")

    len_sel = g.node("list_get", -1460, y_t, {"Defaults": {"index": num(0)}})
    pfx_sel = g.node("list_get", -1460, y_t + 220, {"Defaults": {"index": num(0)}})
    snd_sel = g.node("list_get", -1460, y_t + 440, {"Defaults": {"index": num(0)}})
    g.edge(len_parse, "Array", len_sel, "list")
    g.edge(pfx_parse, "Array", pfx_sel, "list")
    g.edge(snd_parse, "Array", snd_sel, "list")
    g.edge(movie_v, "value", len_sel, "index")
    g.edge(movie_v, "value", pfx_sel, "index")
    g.edge(movie_v, "value", snd_sel, "index")

    len_num = g.node("convert_type", -1240, y_t, {"OutputType": "number"})
    g.edge(len_sel, "value", len_num, "value")

    # ================= FRAME PATH =================
    frame_str = g.node("convert_type", -1240, y_t + 220, {"OutputType": "string"})
    g.edge(frame_v, "value", frame_str, "value")
    cat_one = g.node("string_concat", -1020, y_t + 220, {"Defaults": {"a": string(""), "b": string("")}})
    g.edge(pfx_sel, "value", cat_one, "a")
    g.edge(frame_str, "value", cat_one, "b")
    cat_two = g.node("string_concat", -800, y_t + 220, {"Defaults": {"a": string(""), "b": string(".jpg")}})
    g.edge(cat_one, "value", cat_two, "a")

    # ================= LOGIC =================
    playing_cmp = g.node("compare", -1060, Y + 120, {"Defaults": {"b": num(0), "operator": string(">")}})
    ending_cmp = g.node("compare", -840, Y + 120, {"Defaults": {"operator": string(">=")}})
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

    # ================= WIDGET =================
    image_bindings = {k: v for k, v in json.load(open("/tmp/gng/widget_bindings.json")).items()
                      if k not in ("W", "H", "X", "Y")}
    image_el = {"FontSize": 16, "ManagedWidget": 1, "Scale": 1.0, "Rotation": 0.0, "Italic": 0,
                "X": 0, "Visible": 1, "W": 1536, "Text": "Widget", "H": 864,
                "Color": -1509377, "FontStyle": "regular", "Y": 0, "Bold": 0,
                "Port": "image", "Texture": menu, "PropertyBindings": image_bindings, "Type": "image"}

    elements, dyn_out, ports = [image_el], {}, []
    pick_by_slot = {}
    for s in enabled:
        idx = s["index"]
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
        "WidgetType": "image", "Label": "ACC Display", "WidgetWidth": 140, "WidgetHeight": 72})
    g.edge(show_branch, "value", widget, "image")
    g.edge(btn_w, "value", widget, "width")
    g.edge(btn_h, "value", widget, "height")
    g.edge(snd_sel, "value", play_snd, "sound")

    # ================= BUTTON CHAINS =================
    for i, s in enumerate(enabled):
        idx = s["index"]
        x = -1500 + (i % 6) * 300
        y = Y + 980 + (i // 6) * 260
        const_i = g.node("constant_number", x - 140, y, {"Value": float(idx)})
        set_movie = g.node("variable_set", x + 80, y,
                           {"DynamicOutputs": {"value": "number"},
                            "PersistentPorts": {"input:exec": 1},
                            "DynamicInputs": {"default": "number", "value": "number"},
                            "Defaults": {"default": num(0), "exec": num(0), "type": string("Movie")}})
        g.edge(widget, pick_by_slot[idx], set_movie, "exec")
        g.edge(const_i, "value", set_movie, "value")
        g.edge(set_movie, "exec", start_frame0, "exec")

    # ================= MANIFEST =================
    graph = {"Variables": {"Movie": num(0), "Frame": num(0)},
             "ViewportZoom": 0.25, "Revision": 1, "ViewportY": 200.0, "ViewportX": 1600.0,
             "Nodes": g.nodes, "Edges": g.edges, "Functions": [], "Groups": [],
             "Name": "cinema", "Version": 9}
    graph_id = str(uuid.uuid4())
    sg = {"GraphId": graph_id, "Graph": graph}
    doc = {"schemaVersion": 1, "kind": "contraption_network_linker",
           "linkerManifestId": f"vid_{VERSION}", "linkerId": "",
           "storedGraphs": [sg],
           "linkerData": {"StoredGraphs": [sg], "SelectedGraphId": graph_id},
           "updatedAtGameTime": 0,
           "updatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
           "displayName": f"vid_{VERSION}", "revision": 1}
    return doc


def validate(doc):
    g = doc["storedGraphs"][0]["Graph"]
    nodes, edges = g["Nodes"], g["Edges"]
    ids = {n["Id"] for n in nodes}
    assert len(ids) == len(nodes), "duplicate node id"
    assert len(edges) <= 512 and len(nodes) <= 512, "count limits"
    eids = set()
    for e in edges:
        assert e["FromNode"] in ids and e["ToNode"] in ids, f"dangling edge {e['Id']}"
        key = (e["FromNode"], e["FromPort"], e["ToNode"], e["ToPort"])
        assert key not in eids, f"duplicate edge {key}"
        eids.add(key)
    for n in nodes:
        for k, v in (n.get("Data") or {}).items():
            if k == "Value" and isinstance(v, str):
                assert len(v) < 30000, f"NBT string too long in {n['Id']}"
    for t in [n for n in nodes if n["Type"] == "constant_string"]:
        v = t["Data"]["Value"]
        assert len(v) < 30000
        if v.count("#") > 0:
            assert v.count("#") == 12, "table must have 13 entries"
    js = json.dumps(doc)
    assert len(js) < 250_000, f"serialized too big: {len(js)}"
    print(f"nodes={len(nodes)} edges={len(edges)} json={len(js) / 1024:.1f} KiB -> OK")


def main():
    doc = build()
    validate(doc)
    out = os.path.join(SHARED, f"vid_{VERSION}.json")
    for p in (out, os.path.join(SHARED, "vid.json"), os.path.join(SHARED, "vid_2.json"),
              DOWNLOADS_VID):
        json.dump(doc, open(p, "w"), indent=1)
        print("wrote", p)


if __name__ == "__main__":
    main()
