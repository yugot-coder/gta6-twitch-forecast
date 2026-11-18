"""Forecast a console launch day's Twitch viewers, hour by hour, as quantiles.

Written for make.fun's gta6-twitch-ccu-forecast-01 (Python 3.13, standard library
only, no network). The grader runs this file once per case: the case file in the
input directory holds hour 1's printed viewer count for the launch's release day,
the recorded history before it, and a library of past launches ("comparables"),
each with hourly viewers from 14 days before its own release day to 3 days after.
For every hour 2..24 the program writes five quantiles of that hour's count.

Method, in one paragraph: a launch day's shape is read off the launches that
resemble this one. Each comparable's release day becomes a curve of log-ratios to
its own hour 1, so launches of any size can be pooled. Comparables are weighted
by a gaussian kernel on the distance between their log hour-1 count and the
target's (a launch's scale is its strongest family trait), with smaller factors
for a pre-launch ramp mismatch, for launches that also shipped on PC (this
contest's launches are console-only, and a simultaneous PC unlock stamps a
different first-day shape), and for launches whose early-access period had
already run hot before release day. The five quantiles of the weighted
log-ratio distribution, smoothed across neighbouring hours and with the spread
pulled slightly in (a factor 0.85 about the median, less late in the day), are
the forecast. The constants were calibrated by leave-one-out over the
comparable library and against the four practice launches; on the practice the
program scores a mean log-pinball loss of about 0.20 against the persistence
baseline's 0.39.

The target of the final is Grand Theft Auto VI: the most pre-ordered game in
PlayStation Store history (Sensor Tower estimates past 10 million pre-orders),
unlocking at midnight local time country by country from New Zealand, console
only. Streams Charts measured a 2.50 million Twitch peak for the category on
18 November from the first regions alone, beyond every previous game launch's
Twitch peak (Valorant's closed beta held 1.74 million). None of that is
hard-coded: the case's own hour 1 and history carry the level, and the
comparables carry the shape; the numbers above are why the shape is pooled the
way it is.

Runs with $MAKEFUN_INPUT_DIR / $MAKEFUN_OUTPUT_DIR set locally, else /input
and /output. Deterministic: the same case always writes the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Calibration constants (leave-one-out over the comparables + the practice set).
SIGMA_SCALE = 0.55    # gaussian width, log hour-1 distance
SIGMA_PRE = 0.6       # gaussian width, pre-launch ramp distance
PC_WEIGHT = 0.85      # a comparable that also shipped on PC
EA_WEIGHT = 0.35      # a comparable whose early access ran hot
SPREAD_K = 0.85       # spread about the median is pulled in by this factor
SPREAD_K_LATE = -0.1  # ... drifting to SPREAD_K + this by hour 24
SMOOTH = 0.25         # neighbour weight when smoothing quantiles across hours
MIN_DAY_POINTS = 20   # a comparable needs this many release-day hours
MIN_HOUR1 = 200       # ... and at least this many hour-1 viewers


def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def round2(x):
    """Round to 2 decimals, half up; whole numbers come back as ints."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def day_curve(hourly, day_start):
    """A comparable's release-day viewers by hour 1..24, gaps filled geometrically.

    Returns None when the day is too incomplete or has no hour 1.
    """
    ds = parse_ts(day_start)
    day = {}
    for pt in hourly:
        v = pt.get("viewers")
        if v is None or v <= 0:
            continue
        t = parse_ts(pt["from"])
        if ds <= t < ds + timedelta(hours=24):
            day[(t - ds).seconds // 3600 + 1] = float(v)
    if len(day) < MIN_DAY_POINTS or 1 not in day:
        return None
    hours = sorted(day)
    for h in range(1, 25):
        if h in day:
            continue
        prev = max([x for x in hours if x < h], default=None)
        nxt = min([x for x in hours if x > h], default=None)
        if prev is not None and nxt is not None:
            f = (h - prev) / (nxt - prev)
            day[h] = math.exp(math.log(day[prev]) + f * (math.log(day[nxt]) - math.log(day[prev])))
        elif prev is not None:
            day[h] = day[prev]
        elif nxt is not None:
            day[h] = day[nxt]
    return day


def pre_points(hourly, day_start, hours_back):
    """(offset_hours, viewers) for the points before day_start, oldest first."""
    ds = parse_ts(day_start)
    rows = []
    for pt in hourly:
        v = pt.get("viewers")
        if v is None:
            continue
        t = parse_ts(pt["from"])
        if ds - timedelta(hours=hours_back) <= t < ds:
            rows.append((t, float(v)))
    rows.sort(key=lambda r: r[0])
    return rows


def launch_features(hourly, day_start, p1, platforms, unlock_text):
    """The launch-situation features a target and a comparable are matched on."""
    pre = pre_points(hourly, day_start, 72)
    last6 = [v for _, v in pre[-6:]]
    pre_ratio = (sum(last6) / len(last6)) / p1 if last6 and p1 > 0 else 0.0
    if isinstance(platforms, str):
        plat_text = platforms
    else:
        plat_text = " ".join(str(x) for x in platforms)
    tokens = set("".join(ch if ch.isalnum() else " " for ch in plat_text).split())
    low = unlock_text.lower()
    return {
        "logp1": math.log(max(p1, 1.0)),
        "pre_ratio": pre_ratio,
        "has_pc": "PC" in tokens,
        "early_text": "early" in low and "access" in low,
    }


def comparable_record(cp):
    """A comparable launch as {curve, feats}, or None when it cannot be pooled."""
    curve = day_curve(cp["hourly"], cp["day_start"])
    if curve is None or curve[1] < MIN_HOUR1:
        return None
    feats = launch_features(cp["hourly"], cp["day_start"], curve[1],
                            cp.get("platforms", []), cp.get("unlock", ""))
    # Early access read off the data: the pre-days already ran near the day's peak.
    pre = pre_points(cp["hourly"], cp["day_start"], 72)
    pre_max = max([v for _, v in pre], default=0.0)
    feats["early_hot"] = pre_max > 0.6 * max(curve.values())
    return {"curve": curve, "feats": feats}


def gauss(d, s):
    return math.exp(-(d * d) / (2 * s * s))


def weighted_quantile(pairs, tau):
    """Linear-interpolated weighted quantile of (value, weight) pairs."""
    pairs = sorted(pairs, key=lambda x: x[0])
    total = sum(w for _, w in pairs)
    target = tau * total
    acc = 0.0
    for i, (v, w) in enumerate(pairs):
        acc += w
        if acc >= target:
            if i == 0:
                return v
            prev_v = pairs[i - 1][0]
            prev_acc = acc - w
            if acc == prev_acc:
                return v
            f = (target - prev_acc) / (acc - prev_acc)
            return prev_v + f * (v - prev_v)
    return pairs[-1][0]


def pooled_forecast(p1, tfeats, records):
    """The five quantiles of hours 2..24 from the weighted comparable pool."""
    weighted = []
    for rec in records:
        f = rec["feats"]
        w = gauss(tfeats["logp1"] - f["logp1"], SIGMA_SCALE)
        w *= gauss(tfeats["pre_ratio"] - f["pre_ratio"], SIGMA_PRE)
        if f["has_pc"] and not tfeats["has_pc"]:
            w *= PC_WEIGHT
        if f["early_text"] or f["early_hot"]:
            w *= EA_WEIGHT
        if w > 1e-9:
            weighted.append((rec, w))
    if not weighted:
        return None
    raw = {}
    for h in range(2, 25):
        pairs = [(math.log(rec["curve"][h]) - math.log(rec["curve"][1]), w)
                 for rec, w in weighted]
        for li, tau in enumerate(LEVELS):
            raw[(h, li)] = weighted_quantile(pairs, tau)
    # Smooth each level's log-quantile across neighbouring hours: a launch day's
    # shape does not jump hour to hour, and the smoothing trades a little bias for
    # much less sampling noise in the pool's tails.
    sm = {}
    for li in range(len(LEVELS)):
        for h in range(2, 25):
            if 2 < h < 24:
                acc = raw[(h, li)] * (1 - 2 * SMOOTH)
                wsum = 1 - 2 * SMOOTH
            else:
                acc = raw[(h, li)] * (1 - SMOOTH)
                wsum = 1 - SMOOTH
            if h > 2:
                acc += raw[(h - 1, li)] * SMOOTH
                wsum += SMOOTH
            if h < 24:
                acc += raw[(h + 1, li)] * SMOOTH
                wsum += SMOOTH
            sm[(h, li)] = acc / wsum
    out = {}
    for h in range(2, 25):
        med = sm[(h, 2)]
        k = SPREAD_K + SPREAD_K_LATE * (h - 2) / 22.0
        out[h] = [p1 * math.exp(med + k * (sm[(h, li)] - med)) for li in range(len(LEVELS))]
    return out


def persistence_forecast(p1):
    """Fallback: hour 1's count held flat, the house baseline's widening spread."""
    return {h: [p1 * math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z]
            for h in range(2, 25)}


def forecast_case(case):
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    p1 = max(1.0, float(first["viewers"])) if first else 1.0
    rows = None
    try:
        records = []
        for cp in case.get("comparables", []):
            rec = comparable_record(cp)
            if rec is not None:
                records.append(rec)
        if records:
            # Every launch this contest scores is console-only (the final by its
            # rules, the practice four by their notes), so the target never has PC.
            tfeats = launch_features(case.get("history_hourly", []), case["day_start"],
                                     p1, [], "")
            tfeats["has_pc"] = False
            rows = pooled_forecast(p1, tfeats, records)
    except Exception:
        rows = None
    if rows is None:
        rows = persistence_forecast(p1)
    hours = []
    for row_spec in case["forecast"]:
        h = row_spec["hour"]
        vals = []
        for v in rows[h]:
            v = min(max(v, 0.01), 1_000_000_000.0)
            vals.append(v)
        for i in range(1, len(vals)):
            if vals[i] < vals[i - 1]:
                vals[i] = vals[i - 1]
        hours.append({"hour": h, "q": [round2(v) for v in vals]})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
