#!/usr/bin/env python3
"""Island-Rueckreise-Vergleich: BIRK -> EGPB (UK) vs. BIRK -> ENBR (NOR).

Entscheidungshilfe fuer den Kontinentalruecksprung nach dem Groenland-Leg:
  ROUTE-UK : BIRK - Ingolfshoefdi - Atlantik-Mitte - EGPB Sumburgh
             (weiter England/Irland -> Kontinent), 634 NM
  ROUTE-NOR: BIRK - Ingolfshoefdi - EKVG Vagar - Nordsee - ENBR Bergen
             (weiter Daenemark -> Kontinent), 794 NM

Beide Routen werden je Szenario (ETD BIRK, Standard 0900/1100/1300Z)
vorwaerts durchgerechnet: Ueberflugzeit je Punkt, T/RH auf FL090 und
FL130 (linear in ft zwischen 850/700/500/400 hPa, konservativ inkl.
Standardflaeche binnen +/-1500 ft), Ice-Flags wie Greenland-Evaluator.
Zusaetzlich FOG-Gate am Ziel und am Enroute-Alternate: 2m-Spread
(T2m - Td2m) aus ECMWF-Single-Level, Schwellen fuer maritime
Advektionslagen: < 1.5 K NOGO-Risiko, < 3 K WARN, sonst OK.

VERDICT je Szenario: Rangfolge nach schlechtestem Gate (ICE beste FL,
FOG Ziel), Gleichstand nach Flugzeit (Segmentwind 700 hPa), dann nach
Ziel-Spread. Statische Faktoren (Schengen, GAR, Wasserstrecken,
Alternates) stehen im README — sie kippen nicht per Wetterlauf.

TAS 60% abgeleitet aus AFM-Ankern (keine Zitate): F090 151, F130 156 kt.
Aufruf: iceland_return.py [YYYY-MM-DD] [ETD1,ETD2,... HHMM = ETD BIRK]
Ice-Flags bewusst ueberwarnend. Planungshilfe, keine PIC-Entscheidung.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

UA = {"User-Agent": "TTA-IcelandReturn/1.0 (private expedition briefing)"}
AWC = "https://aviationweather.gov/api/data"
OUT_TXT = "iceland_return.txt"

LEVELS = [850, 700, 500, 400]
LEVEL_FT = {850: 4780, 700: 9880, 500: 18280, 400: 23570}
ICE_T_MAX, ICE_T_MIN = 0.0, -16.0
ICE_RH, ICE_RH_MOD = 85.0, 95.0
FL_FT = {"F090": 9000, "F130": 13000}
FL_TAS = {"F090": 151.0, "F130": 156.0}
NEAR_LVL = {"F090": 700}
FLS = ("F090", "F130")
HW_GUESS = 5.0                    # kt, ostwaerts eher Rueckenwind unsicher
SPREAD_NOGO, SPREAD_WARN = 1.5, 3.0

RANK = {"-": 0, "ICE?": 1, "ICE!": 2}
STATUS = {0: "OK", 1: "WARN", 2: "NOGO"}

@dataclass(frozen=True)
class WPT:
    name: str
    lat: float
    lon: float

ROUTES: dict[str, list[WPT]] = {
    "UK": [
        WPT("BIRK Reykjavik",     64.13, -21.94),
        WPT("Ingolfshoefdi",      63.80, -16.65),
        WPT("Atlantik-Mitte",     62.30, -9.50),
        WPT("EGPB Sumburgh",      59.88, -1.30),
    ],
    "NOR": [
        WPT("BIRK Reykjavik",     64.13, -21.94),
        WPT("Ingolfshoefdi",      63.80, -16.65),
        WPT("EKVG Vagar",         62.06, -7.28),
        WPT("Nordsee-Mitte",      61.20, -1.00),
        WPT("ENBR Bergen",        60.29, 5.22),
    ],
    "UK2": [
        WPT("EGPB Sumburgh",      59.88, -1.30),
        WPT("EGNT Nordengland",   55.04, -1.69),
        WPT("Kanal Dover",        51.10, 1.35),
        WPT("EDDK Rheinland",     50.87, 7.14),
    ],
    "NOR2": [
        WPT("ENBR Bergen",        60.29, 5.22),
        WPT("Skagerrak",          57.60, 7.60),
        WPT("EKBI Billund",       55.74, 9.15),
        WPT("EDDV Norddeutschl",  52.46, 9.68),
    ],
}
DAY2 = {"UK": "UK2", "NOR": "NOR2"}
# FOG-Gate-Punkte: (Routenname, Punktindex, Label)
FOG_PTS = {"UK": [(3, "EGPB")], "NOR": [(2, "EKVG"), (4, "ENBR")],
           "UK2": [(0, "EGPB")], "NOR2": [(2, "EKBI")]}
STATIONS = ("BIRK", "BIEG", "EGPB", "EGPC", "EKVG", "ENBR", "ENZV",
            "EGNT", "EDDK", "EKBI", "EDDV")


def die(msg: str) -> None:
    print(f"ABBRUCH: {msg}", file=sys.stderr)
    sys.exit(1)


# ----------------------------------------------------------------- Geometrie
def gc_nm(a: WPT, b: WPT) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dl = math.radians(b.lon - a.lon)
    return math.acos(min(1.0, math.sin(p1) * math.sin(p2)
                         + math.cos(p1) * math.cos(p2) * math.cos(dl))) * 3440.065


def course_true(a: WPT, b: WPT) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dl = math.radians(b.lon - a.lon)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360.0

SEG = {r: {"nm": [gc_nm(w[i], w[i + 1]) for i in range(len(w) - 1)],
           "tc": [course_true(w[i], w[i + 1]) for i in range(len(w) - 1)]}
       for r, w in ROUTES.items()}
ALL_WPTS = {w.name: w for r in ROUTES.values() for w in r}


# ------------------------------------------------------------------- Zeiten
def flight_day(now: datetime, override: str | None) -> datetime:
    if override:
        return datetime.strptime(override, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (now + timedelta(days=1) if now.hour >= 12 else now).replace(
        hour=0, minute=0, second=0, microsecond=0)


def parse_times(day: datetime, arg: str | None) -> list[datetime]:
    raw = (arg or "0900,1100,1300").split(",")
    out = []
    for s in raw:
        s = s.strip()
        if len(s) != 4 or not s.isdigit():
            die(f"ETD '{s}' nicht als HHMM lesbar")
        out.append(day.replace(hour=int(s[:2]), minute=int(s[2:])))
    return out


def seg_headwind(prof: dict, tc: float) -> float:
    u, v = prof[700]["u"], prof[700]["v"]
    rad = math.radians(tc)
    return -(u * math.sin(rad) + v * math.cos(rad)) * 1.9438


def times_forward(route: str, etd: datetime, tas: float,
                  wind_fn=None) -> tuple[list[datetime], list[float], float]:
    """Vorwaerts ab ETD. Rueckgabe: (Punktzeiten, Segment-HW, Gesamt-h)."""
    nm, n = SEG[route]["nm"], len(ROUTES[route])
    hw = [HW_GUESS] * (n - 1)
    t = [etd] * n
    for _ in range(2 if wind_fn else 1):
        for i in range(n - 1):
            gs = max(60.0, tas - hw[i])
            t[i + 1] = t[i] + timedelta(hours=nm[i] / gs)
        if wind_fn:
            for i in range(n - 1):
                mid = t[i] + (t[i + 1] - t[i]) / 2
                hw[i] = wind_fn(route, i, mid)
    return t, hw, (t[-1] - t[0]).total_seconds() / 3600.0


# ------------------------------------------------------------- Ableitungen
def ice_flag(t: float, rh: float) -> str:
    if ICE_T_MIN <= t <= ICE_T_MAX:
        if rh >= ICE_RH_MOD:
            return "ICE!"
        if rh >= ICE_RH:
            return "ICE?"
    return "-"


def at_ft(prof: dict, ft: int) -> tuple[float, float]:
    lv = sorted(LEVELS, reverse=True)
    if ft <= LEVEL_FT[lv[0]]:
        return prof[lv[0]]["t"], prof[lv[0]]["rh"]
    for lo, hi in zip(lv, lv[1:]):
        if LEVEL_FT[lo] <= ft <= LEVEL_FT[hi]:
            f = (ft - LEVEL_FT[lo]) / (LEVEL_FT[hi] - LEVEL_FT[lo])
            return (prof[lo]["t"] + f * (prof[hi]["t"] - prof[lo]["t"]),
                    prof[lo]["rh"] + f * (prof[hi]["rh"] - prof[lo]["rh"]))
    return prof[400]["t"], prof[400]["rh"]


def fl_eval(prof: dict, fl: str) -> tuple[str, float, float]:
    t, rh = at_ft(prof, FL_FT[fl])
    flag = ice_flag(t, rh)
    near = NEAR_LVL.get(fl)
    if near is not None:
        f2 = ice_flag(prof[near]["t"], prof[near]["rh"])
        if RANK[f2] > RANK[flag]:
            flag = f2
    return flag, t, rh


def spread_rank(spread: float) -> int:
    return 2 if spread < SPREAD_NOGO else 1 if spread < SPREAD_WARN else 0


def interp(data: dict, grid: list[datetime], wname: str,
           when: datetime, key: str):
    """Zeitliche Interpolation; key 'pl' = Profil, '2m' = (t2m, td2m)."""
    if when <= grid[0]:
        return data[grid[0]][wname][key]
    if when >= grid[-1]:
        return data[grid[-1]][wname][key]
    for g1, g2 in zip(grid, grid[1:]):
        if g1 <= when <= g2:
            f = (when - g1) / (g2 - g1)
            a, b = data[g1][wname][key], data[g2][wname][key]
            if key == "2m":
                return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
            return {lvl: {k: a[lvl][k] + f * (b[lvl][k] - a[lvl][k])
                          for k in ("t", "rh", "u", "v")} for lvl in LEVELS}
    return data[grid[-1]][wname][key]


# --------------------------------------------------------------- Bewertung
def eval_route(data: dict, grid: list[datetime], route: str,
               etd: datetime) -> dict:
    def wind_fn(r: str, i: int, mid: datetime) -> float:
        prof = interp(data, grid, ROUTES[r][i].name, mid, "pl")
        return seg_headwind(prof, SEG[r]["tc"][i])

    # Timing mit F090-TAS als Referenz (Delta F130 < 5 min, s. Header)
    t, hw, hours = times_forward(route, etd, FL_TAS["F090"], wind_fn)

    lines = [f"--- ROUTE-{route}  ETD {ROUTES[route][0].name.split()[0]} {etd:%H%M}Z  "
             f"ETA {t[-1]:%H%M}Z  ({hours:4.1f} h) ---",
             f"{'Punkt':<18}{'Zeit':>6}{'HW':>5}  {'F090':^14}{'F130':^14}"]
    ice: dict[str, int] = {fl: 0 for fl in FLS}
    for i, w in enumerate(ROUTES[route]):
        prof = interp(data, grid, w.name, t[i], "pl")
        cells = []
        for fl in FLS:
            flag, tt, rh = fl_eval(prof, fl)
            ice[fl] = max(ice[fl], RANK[flag])
            cells.append(f"{tt:>5.1f}/{rh:>3.0f} {flag:<4}")
        hwtxt = f"{hw[i]:+4.0f}" if i < len(hw) else "    "
        lines.append(f"{w.name:<18}{t[i]:%H%M}Z{hwtxt:>5}  "
                     + "".join(f"{c:^14}" for c in cells))

    fog_rank, fog_txt = 0, []
    for idx, label in FOG_PTS[route]:
        t2, td2 = interp(data, grid, ROUTES[route][idx].name, t[idx], "2m")
        sp = t2 - td2
        r = spread_rank(sp)
        fog_rank = max(fog_rank, r)
        fog_txt.append(f"{label} {sp:.1f}K:{STATUS[r]}")

    best_fl = min(FLS, key=lambda fl: (ice[fl], FLS.index(fl)))
    total = max(ice[best_fl], fog_rank)
    lines.append(f"ICE " + " ".join(f"{fl}:{STATUS[ice[fl]]}" for fl in FLS)
                 + f" | FOG " + " ".join(fog_txt)
                 + f" | BEST {best_fl} => [{STATUS[total]}]")
    return {"lines": lines, "rank": total, "hours": hours,
            "best_fl": best_fl, "ice": ice[best_fl], "fog": fog_rank,
            "eta": t[-1]}


def scenario(data: dict, grid: list[datetime], etd: datetime) -> list[str]:
    lines = ["", f"=== SZENARIO ETD {etd:%H%M}Z  "
                 f"(Tag 1 {etd:%d.%m.}, Folgetag {etd + timedelta(days=1):%d.%m.} "
                 f"gleiche ETD) ==="]
    res: dict[str, dict] = {}
    for route in ("UK", "NOR"):
        d1 = eval_route(data, grid, route, etd)
        d2 = eval_route(data, grid, DAY2[route], etd + timedelta(days=1))
        lines += d1["lines"] + d2["lines"] + [""]
        res[route] = {"rank": max(d1["rank"], d2["rank"]),
                      "hours": d1["hours"] + d2["hours"],
                      "fog": max(d1["fog"], d2["fog"]),
                      "d1": d1, "d2": d2}
    uk, no = res["UK"], res["NOR"]
    if uk["rank"] != no["rank"]:
        pick = "UK" if uk["rank"] < no["rank"] else "NOR"
        why = "Wettergates"
    elif abs(uk["hours"] - no["hours"]) > 0.4:
        pick = "UK" if uk["hours"] < no["hours"] else "NOR"
        why = "Gesamtflugzeit"
    elif uk["fog"] != no["fog"]:
        pick = "UK" if uk["fog"] < no["fog"] else "NOR"
        why = "Spread-Gates"
    else:
        pick = "NOR"
        why = "Gleichstand, kuerzere Gesamtstrecke nach LOWG"
    dt = abs(uk["hours"] - no["hours"]) * 60
    lines.append(
        f"VERDICT UK:[{STATUS[uk['rank']]}] "
        f"{uk['d1']['hours']:.1f}+{uk['d2']['hours']:.1f}h "
        f"T1:{STATUS[uk['d1']['rank']]}/T2:{STATUS[uk['d2']['rank']]} | "
        f"NOR:[{STATUS[no['rank']]}] "
        f"{no['d1']['hours']:.1f}+{no['d2']['hours']:.1f}h "
        f"T1:{STATUS[no['d1']['rank']]}/T2:{STATUS[no['d2']['rank']]} | "
        f"EMPFEHLUNG: {pick} ({why}, dT {dt:.0f} min)")
    return lines


# ------------------------------------------------------------------- Daten
def fetch_ecmwf(day: datetime) -> tuple[dict, list[datetime]]:
    try:
        from ecmwf.opendata import Client
        import xarray as xr
        import tempfile, os
    except ImportError as e:
        die(f"Modul fehlt: {e}")
    client = Client(source="ecmwf")
    latest = client.latest(type="fc", param="t")
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    steps, grid = [], []
    for d in (day, day + timedelta(days=1)):
        for h in range(6, 22, 3):
            vt = d.replace(hour=h)
            st = int((vt - latest).total_seconds() // 3600)
            if 0 <= st <= 141:
                steps.append(st)
                grid.append(vt)
    if not steps:
        die("Kein Modellschritt deckt den Flugtag")
    data: dict = {vt: {} for vt in grid}
    with tempfile.TemporaryDirectory() as td:
        fpl = os.path.join(td, "pl.grib2")
        client.retrieve(type="fc", step=steps, levtype="pl",
                        levelist=LEVELS, param=["t", "r", "u", "v"],
                        target=fpl)
        dpl = xr.open_dataset(fpl, engine="cfgrib")
        fsl = os.path.join(td, "sfc.grib2")
        client.retrieve(type="fc", step=steps, levtype="sfc",
                        param=["2t", "2d"], target=fsl)
        dsl = xr.open_dataset(fsl, engine="cfgrib")
        for vt, st in zip(grid, steps):
            spl = dpl.sel(step=timedelta(hours=st))
            ssl = dsl.sel(step=timedelta(hours=st))
            for w in ALL_WPTS.values():
                ppl = spl.sel(latitude=w.lat, longitude=w.lon % 360,
                              method="nearest")
                psl = ssl.sel(latitude=w.lat, longitude=w.lon % 360,
                              method="nearest")
                data[vt][w.name] = {
                    "pl": {lvl: {"t": float(ppl["t"].sel(isobaricInhPa=lvl))
                                      - 273.15,
                                 "rh": float(ppl["r"].sel(isobaricInhPa=lvl)),
                                 "u": float(ppl["u"].sel(isobaricInhPa=lvl)),
                                 "v": float(ppl["v"].sel(isobaricInhPa=lvl))}
                           for lvl in LEVELS},
                    "2m": (float(psl["t2m"]) - 273.15,
                           float(psl["d2m"]) - 273.15)}
    return data, grid


def fetch_metars() -> list[str]:
    out = ["", "METAR/TAF (AWC)", "-" * 60]
    try:
        with httpx.Client(headers=UA, timeout=30) as c:
            r = c.get(f"{AWC}/metar",
                      params={"ids": ",".join(STATIONS), "format": "raw",
                              "taf": "true", "hours": 3})
            out += [ln for ln in r.text.splitlines() if ln.strip()]
    except Exception as e:                        # noqa: BLE001
        out.append(f"(nicht abrufbar: {e})")
    return out


# -------------------------------------------------------------------- Main
def main() -> None:
    now = datetime.now(timezone.utc)
    day = flight_day(now, sys.argv[1] if len(sys.argv) > 1 else None)
    etds = parse_times(day, sys.argv[2] if len(sys.argv) > 2 else None)

    data, grid = fetch_ecmwf(day)

    tot = {r: sum(SEG[r]["nm"]) for r in SEG}
    lines = [f"ICELAND RETURN — ROUTENVERGLEICH UK vs. NOR — "
             f"Tag 1 {day:%d.%m.%Y}, Folgetag {day + timedelta(days=1):%d.%m.}",
             f"Erstellt {now:%d.%m. %H%M}Z | ECMWF oper 0.25 | "
             f"UK {tot['UK']:.0f}+{tot['UK2']:.0f} NM | "
             f"NOR {tot['NOR']:.0f}+{tot['NOR2']:.0f} NM | "
             f"nach LOWG gesamt ~1806 vs ~1689 NM",
             "FL-Optionen F090/F130 | FOG = 2m-Spread ECMWF am Ziel/Alt "
             f"(<{SPREAD_NOGO}K NOGO, <{SPREAD_WARN}K WARN) | "
             "Folgetag: EGPB-EGNT-Dover-EDDK vs. ENBR-EKBI-EDDV, gleiche ETD. Statik im README."]
    for etd in etds:
        lines += scenario(data, grid, etd)
    lines += fetch_metars()
    lines += ["", "Ice-Flags RH-basiert, bewusst ueberwarnend. TAS abgeleitet "
                  "aus AFM-Ankern. Planungshilfe, keine PIC-Entscheidung."]

    text = "\n".join(lines)
    print(text)
    try:
        with open(OUT_TXT, "w") as f:
            f.write(text + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    main()
