"""Shared collection logic for TA-amdgpu scripted inputs (/sys/class/drm + /sys/class/kfd)."""
import json
import os
import re
import sys

DRM = "/sys/class/drm"
KFD = "/sys/class/kfd"
AMD_VENDOR = "0x1002"

CARD_RE = re.compile(r"^card(\d+)$")


def read_file(path):
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return None


def _int(x):
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return None


def _hwmon_dir(card_dir, card_name):
    for cand in (
        os.path.join(card_dir, "device", "hwmon"),
        os.path.join(card_dir, "hwmon"),
        os.path.join(card_dir, card_name, "hwmon"),
    ):
        if not os.path.isdir(cand):
            continue
        try:
            subs = sorted(os.listdir(cand))
        except OSError:
            subs = []
        for sub in subs:
            if sub.startswith("hwmon"):
                sub_dir = os.path.join(cand, sub)
                if os.path.isfile(os.path.join(sub_dir, "temp1_input")):
                    return sub_dir
        if os.path.isfile(os.path.join(cand, "temp1_input")):
            return cand
    return None


def _collect_card(card_dir, card_name):
    rec = {}
    v = _int(read_file(os.path.join(card_dir, "device", "gpu_busy_percent")))
    if v is not None:
        rec["busy_pct"] = v
    v = _int(read_file(os.path.join(card_dir, "device", "mem_info_vram_used")))
    if v is not None:
        rec["vram_used_mib"] = v // 1048576
    v = _int(read_file(os.path.join(card_dir, "device", "mem_info_vram_total")))
    if v is not None:
        rec["vram_total_mib"] = v // 1048576
    hm = _hwmon_dir(card_dir, card_name)
    if hm is not None:
        t = _int(read_file(os.path.join(hm, "temp1_input")))
        if t is not None:
            rec["temperature_c"] = t / 1000.0
    return rec


def discover():
    cards = {}
    try:
        names = os.listdir(DRM)
    except OSError:
        names = []
    for name in sorted(names):
        if not CARD_RE.match(name):
            continue
        card_dir = os.path.join(DRM, name)
        vendor = read_file(os.path.join(os.path.realpath(card_dir), "device", "vendor"))
        if vendor is None or vendor.lower() != AMD_VENDOR:
            continue
        cards[name] = _collect_card(card_dir, name)
    return {
        "status": "ok" if cards else "absent",
        "gpu_count": len(cards),
        "kfd": 1 if os.path.isdir(KFD) else 0,
        "cards": cards,
    }


def metrics_payload(data):
    payload = {
        "gpu_count": data.get("gpu_count", 0),
        "kfd": data.get("kfd", 0),
    }
    for name, rec in (data.get("cards") or {}).items():
        for key, val in rec.items():
            if val is None:
                continue
            payload["%s_%s" % (name, key)] = val
    return payload


def emit(payload):
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()


def fail(message):
    sys.stderr.write("TA-amdgpu collection error: %s\n" % message)
    return 1
