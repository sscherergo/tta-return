# TTA Iceland Return — Routenvergleich UK vs. NOR

Entscheidungshilfe fuer den Kontinentalruecksprung ab BIRK nach dem
Groenland-Leg. Zwei Kandidaten, ein Dashboard, ein VERDICT je
ETD-Szenario.

## Routen

| | ROUTE-UK | ROUTE-NOR |
|---|---|---|
| Kette | BIRK – Ingolfshoefdi – Atlantik-Mitte – **EGPB Sumburgh** | BIRK – Ingolfshoefdi – **EKVG Vagar** – Nordsee – **ENBR Bergen** |
| Distanz Erstleg | **634 NM** | 794 NM |
| laengste Wasserstrecke | **~493 NM** (Ingolfshoefdi–EGPB, Alternate-Luecke zwischen BIEG und EGPC) | ~276 NM (–EKVG) + ~377 NM (EKVG–ENBR); **EKVG als Zwischenstation teilt die Strecke** |
| Folgetag (im Lauf) | EGPB – EGNT – Kanal Dover – **EDDK Rheinland**, 771 NM | ENBR – Skagerrak – EKBI – **EDDV Norddeutschland**, 498 NM |
| Rest nach LOWG | ab EDDK ~401 NM | ab EDDV ~397 NM |
| **Gesamt BIRK->LOWG** | **~1806 NM** (634+771+401) | **~1689 NM** (794+498+397) |
| Alternates Erstleg | BIEG, EKVG (nahe Kurs), EGPC Wick, EGPA Kirkwall | BIEG, EKVG, ENZV Stavanger, ENAL Alesund |

## Statische Faktoren (aendern sich nicht pro Wetterlauf)

**Fuer NOR:**
- **Gesamtstrecke nach LOWG ~117 NM kuerzer** und besser balanciert
  (794/498 vs. 634/771 NM) — der laengere Erstsprung kehrt sich ueber
  die Gesamtroute um.
- **Durchgehend Schengen** (Island, Faeroeer via Daenemark*, Norwegen,
  Daenemark, Deutschland, Oesterreich): keine Grenzformalitaeten im
  Sinne der Personenkontrolle. *Faeroeer sind nicht EU, Zollstatus bei
  Landung EKVG separat pruefen (AIP Faeroeer/Danmark) — reiner
  Ueberflug unkritisch.
- Kuerzere einzelne Wasserstrecken, EKVG teilt die Nordatlantik-Etappe.
- Norwegische Westkueste: dichte Platzkette suedwaerts als Alternates.

**Fuer UK:**
- **160 NM kuerzer** auf dem Erstleg, insgesamt bekannte Strecke:
  EGPB wurde auf dem Hinflug genutzt (egpb_leg im Hauptrepo), Charts,
  Verfahren und Handling bekannt.
- **Aber: UK = non-Schengen.** GAR (General Aviation Report) vor
  Einflug, Zoll/Immigration; bei Weiterflug Irland CTA-Sonderregeln;
  Wiedereintritt Schengen am Kontinent mit erneuten Formalitaeten.
- EGPB-Sommerproblem **Haar** (Nordsee-Advektionsnebel) — genau dafuer
  das FOG-Gate.

**Neutral:** Beide Routen unter FL285, Reykjavik/Scottish bzw.
Stavanger FIR — GSR-56-Iridium ausreichend, kein HF-Thema. Jet A1 an
allen genannten Plaetzen. Regulatorische Angaben hier sind
Planungsnotizen aus dem Projektkontext, **vor Ausfuehrung gegen
aktuelle AIPs/NOTAMs verifizieren** (UK GAR-Fristen, EKVG PPR/Zoll,
ENBR Handling).

## Dashboard-Logik

`iceland_return.py` rechnet je ETD-Szenario (Standard 0900/1100/1300Z)
**zwei Tage**: Tag 1 den Erstsprung, den Folgetag die Weiterfuehrung
mit **gleicher ETD** (Modell: gleicher Tagesrhythmus). ECMWF-Open-Data
(0.25 oper, Steps bis 141 h decken beide Tage):

- **ICE-Gates** je Routenpunkt zur Ueberflugzeit auf **F090 und F130**
  (T/RH linear in ft zwischen 850/700/500/400 hPa, konservativ inkl.
  Standardflaeche binnen 1500 ft; Schwellen RH 85/95 %,
  T-Fenster 0…−16 °C — bewusst ueberwarnend, ECMWF-Glazierungs-Bias).
- **FOG-Gate**: 2m-Spread (T2m−Td2m). Tag 1: EGPB bzw. EKVG + ENBR.
  Folgetag: **EGPB am Morgen (Abflug — Haar-Fenster!)** bzw. EKBI.
  < 1.5 K NOGO-Risiko, < 3 K WARN.
- **Timing**: Segmentwind 700 hPa, zwei Iterationen; TAS 60 %
  abgeleitet aus AFM-Ankern FL100 152 kt / FL195 165 kt (keine
  AFM-Zitate).
- **VERDICT**: kombinierte Gates beider Tage → Gesamtflugzeit
  (> 24 min Delta) → Spread-Gates. Bei echtem Gleichstand NOR
  (kuerzere Gesamtstrecke). Format der VERDICT-Zeile enthaelt
  T1/T2-Status je Route.

Ausgabe: `iceland_return.txt` (Root), Anzeige `index.html`
(GitHub Pages, main/root).

## Betrieb

Manueller Dispatch (kein Cron): Actions → iceland-return →
Run workflow. Felder leer = Standard-ETDs, naechster sinnvoller Tag
(vor 12Z: heute, danach: morgen).

METAR/TAF-Anhang: BIRK, BIEG, EGPB, EGPC, EKVG, ENBR, ENZV, EGNT,
EDDK, EKBI, EDDV via AWC.

Planungshilfe. NAV-CANADA-/Met-Office-/IMO-/MET-Norway-Produkte und
das amtliche Briefing bleiben massgeblich; keine PIC-Entscheidung.
