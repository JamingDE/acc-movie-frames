#!/usr/bin/env python3
"""Builds vid_3.0.0.json - ACC Cinema, REDSTONE-LINK edition (no audio, no menu).

One ACC, six movie slots. Each slot is triggered by a Create Redstone Link
(transmit mode) whose frequency (two item slots) matches the slot's
wireless_frequency_input node. Playback = proven vid_1.1.1 recipe
(event_periodic period 3 = 6.67 fps, URL frames, unpadded names).
When the movie runs out of frames the screen goes BLACK until the next
redstone trigger (transmitter falling edge is ignored, movie always plays
to the end once started).

Bytecode-verified mechanics (G&G 1.2.3):
  - wireless_frequency_input: Data.BindingId must be one of the 13 built-in
    AnalogueControlChannel ids (pitch_up ... lift_down). applyGraphBindings ->
    setChannelInputFrequency(channel, FrequencyFirst/Second item ids) registers
    a ControllerLinkInputTarget in Create's REDSTONE_LINK_NETWORK_HANDLER.
  - Create redstone links on the same item pair push strength 0..15 ->
    channel value = strength/15. Value CHANGES enqueue "channel:<id>" events
    -> the node's exec fires. Outputs: value (0..1), active (bool).
  - So: exec fires on BOTH rising and falling edge -> gate through a branch
    on 'active' so only the rising edge starts the movie.

Reads rs_slots.json. Usage: python3 build_cinema_redstone_graph.py [--version N]
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

BLACK = (
         "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDACAWGBwYFCAcGhwkIiAmMFA0MCwsMGJGSjpQd"
         "GZ6eHJmcG6AkLicgIiuim5woNqirr7EztDOfJri8uDI8LjKzsb/2wBDASIkJDAqMF40NF7GhHCExsbGxsbGxsbGxsbGx"
         "sbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsb/wAARCAAJABADASIAAhEBAxEB/8QAHwAAAQUBAQEBA"
         "QEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0Kxw"
         "RVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJi"
         "pKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAH"
         "wEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiM"
         "oEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3e"
         "Hl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09"
         "fb3+Pn6/9oADAMBAAIRAxEAPwDn6KKKAP/Z")


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
    cfg = json.load(open(os.path.join(HERE, "rs_slots.json")))
    slots = cfg["slots"]
    assert len(slots) == 6, "this edition wants exactly 6 redstone slots"

    # tables: index 0 = dummy, 1..6 = slots ('-' so no empty strings survive '#'-split)
    len_table = "#".join(["0"] + [str(s["frames"]) for s in slots])
    pfx_table = "#".join(["-"] + [s["prefix"] or "-" for s in slots])

    g = G()
    Y = 120

    # ---- redstone triggers: one chain per slot ------------------------------
    # wireless_frequency_input --exec--> branch(condition=active) --true-->
    #   Movie=i --> Frame=1.   false (falling edge) does nothing.
    start_frame1 = None
    for i, s in enumerate(slots):
        row_y = Y + i * 320
        wi = g.node("wireless_frequency_input", -2750, row_y, {
            "BindingId": s["channel"],
            "BindingLabel": f"Movie {i + 1} - {s['first'].split(':')[-1]}",
            "FrequencyFirst": s["first"],
            "FrequencySecond": s["second"],
        }, f"Link In {i + 1}")
        br = g.node("branch", -2500, row_y)
        g.edge(wi, "exec", br, "exec")
        g.edge(wi, "active", br, "condition")
        const_i = g.node("constant_number", -2500, row_y + 180, {"Value": float(i + 1)})
        set_movie = g.node("variable_set", -2250, row_y, var_set("Movie"))
        g.edge(br, "true", set_movie, "exec")
        g.edge(const_i, "value", set_movie, "value")
        if start_frame1 is None:
            start_frame1 = g.node("variable_set", -2000, row_y + 640, var_set("Frame"))
        g.edge(set_movie, "exec", start_frame1, "exec")

    # ---- clock: 6.67 fps, advances only while playing ----------------------
    tick = g.node("event_periodic", -1500, Y,
                  {"Period": period, "Defaults": {"period": num(period)}})
    br_playing = g.node("branch", -1280, Y)
    br_end = g.node("branch", -1060, Y)
    g.edge(tick, "exec", br_playing, "exec")

    const_zero = g.node("constant_number", -1500, Y + 660, {"Value": 0.0})
    const_one = g.node("constant_number", -1320, Y + 660, {"Value": 1.0})

    end_movie0 = g.node("variable_set", -840, Y, var_set("Movie"))
    end_frame0 = g.node("variable_set", -620, Y, var_set("Frame"))
    tick_frame = g.node("variable_set", -840, Y + 560, var_set("Frame"))

    g.edge(br_playing, "true", br_end, "exec")
    g.edge(br_end, "true", end_movie0, "exec")
    g.edge(end_movie0, "exec", end_frame0, "exec")
    g.edge(br_end, "false", tick_frame, "exec")
    g.edge(const_zero, "value", end_movie0, "value")
    g.edge(const_zero, "value", end_frame0, "value")
    g.edge(const_one, "value", start_frame1, "value")

    # ---- data: counters ----------------------------------------------------
    movie_v = g.node("variable_get", -1280, Y + 240, {"DynamicOutputs": {"value": "number"}, "Variable": "Movie"})
    frame_v = g.node("variable_get", -1060, Y + 240, {"DynamicOutputs": {"value": "number"}, "Variable": "Frame"})
    add_one = g.node("add", -840, Y + 240, {"Defaults": {"b": num(1)}})
    g.edge(frame_v, "value", add_one, "a")
    g.edge(add_one, "value", tick_frame, "value")

    # ---- tables (index 0 = dummy) -----------------------------------------
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

    # ---- URL = prefix + str(Frame) + ".jpg" -------------------------------
    frame_str = g.node("convert_type", -1240, y_t + 220, {"OutputType": "string"})
    g.edge(frame_v, "value", frame_str, "value")
    cat_one = g.node("string_concat", -1020, y_t + 220,
                     {"Defaults": {"a": string(""), "b": string("")}})
    g.edge(pfx_sel, "value", cat_one, "a")
    g.edge(frame_str, "value", cat_one, "b")
    cat_two = g.node("string_concat", -800, y_t + 220,
                     {"Defaults": {"a": string(""), "b": string(".jpg")}})
    g.edge(cat_one, "value", cat_two, "a")

    # ---- logic ------------------------------------------------------------
    playing_cmp = g.node("compare", -1060, Y + 120,
                         {"Defaults": {"b": num(0), "operator": string(">")}})
    ending_cmp = g.node("compare", -840, Y + 120,
                        {"Defaults": {"operator": string(">")}})
    len_pos_cmp = g.node("compare", -1020, y_t,
                         {"Defaults": {"b": num(0), "operator": string(">")}})
    g.edge(movie_v, "value", playing_cmp, "a")
    g.edge(add_one, "value", ending_cmp, "a")
    g.edge(len_num, "value", ending_cmp, "b")
    g.edge(len_num, "value", len_pos_cmp, "a")
    g.edge(playing_cmp, "value", br_playing, "condition")
    g.edge(ending_cmp, "value", br_end, "condition")

    # ---- blackscreen: empty slot or finished movie -> black ---------------
    black_const = g.node("constant_string", -800, y_t + 420, {"Value": BLACK})
    show_slot = g.node("data_branch", -580, y_t + 220,
                       {"Defaults": {"true": string(""), "false": string("")}})
    show_final = g.node("data_branch", -360, y_t + 220,
                        {"Defaults": {"true": string(""), "false": string("")}})
    g.edge(len_pos_cmp, "value", show_slot, "condition")
    g.edge(cat_two, "value", show_slot, "true")
    g.edge(black_const, "value", show_slot, "false")
    g.edge(playing_cmp, "value", show_final, "condition")
    g.edge(show_slot, "value", show_final, "true")
    g.edge(black_const, "value", show_final, "false")

    # ---- widget: design space == surface px, single image element ---------
    image_bindings = {k: v for k, v in json.load(open("/tmp/gng/widget_bindings.json")).items()
                      if k not in ("W", "H", "X", "Y")}
    image_el = {"FontSize": 16, "ManagedWidget": 1, "Scale": 1.0, "Rotation": 0.0, "Italic": 0,
                "X": 0, "Visible": 1, "W": SURF_W, "Text": "Widget", "H": SURF_H,
                "Color": -1509377, "FontStyle": "regular", "Y": 0, "Bold": 0,
                "Port": "image", "Texture": BLACK, "PropertyBindings": image_bindings,
                "Type": "image"}

    defaults = json.load(open("/tmp/gng/widget_defaults.json"))
    defaults["image"] = string(BLACK)

    widget = g.node("acc_display_widget", 200, Y + 200, {
        "WidgetElements": [image_el],
        "DynamicInputs": {"image": "string"},
        "HudFieldLabels": {"image": "image"},
        "Defaults": defaults,
        "WidgetType": "image", "Label": "ACC Display",
        "WidgetWidth": SURF_W, "WidgetHeight": SURF_H})
    g.edge(show_final, "value", widget, "image")

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


def validate(doc, slots):
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
    chans = set()
    for n in nodes:
        if n["Type"] == "constant_string":
            v = n["Data"]["Value"]
            assert len(v) < 30000
            if v.count("#"):
                assert v.count("#") == 6, "table needs 7 entries"
                for part in v.split("#"):
                    if part.startswith("http"):
                        assert len(part) < 2000 and part.endswith(("/", "g_", "f_", "jpg")), part
        if n["Type"] == "wireless_frequency_input":
            d = n["Data"]
            assert d["BindingId"] == d["BindingId"].strip().lower()
            assert d["FrequencyFirst"].startswith("minecraft:") and d["FrequencySecond"].startswith("minecraft:")
            chans.add(d["BindingId"])
        assert n["Type"] != "play_sound"
    assert len(chans) == 6 and len({s["channel"] for s in slots}) == 6
    js = json.dumps(doc)
    assert len(js) < 250_000
    print(f"nodes={len(nodes)} edges={len(edges)} json={len(js)/1024:.1f} KiB -> OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="3.0.0")
    args = ap.parse_args()
    cfg = json.load(open(os.path.join(HERE, "rs_slots.json")))
    doc = build(cfg["period"])
    doc["linkerManifestId"] = f"vid_{args.version}"
    doc["displayName"] = f"vid_{args.version}"
    validate(doc, cfg["slots"])
    for p in (os.path.join(SHARED, f"vid_{args.version}.json"),
              os.path.join(SHARED, "vid.json"), os.path.join(SHARED, "vid_2.json"),
              DOWNLOADS_VID):
        json.dump(doc, open(p, "w"), indent=1)
        print("wrote", p)


if __name__ == "__main__":
    main()
