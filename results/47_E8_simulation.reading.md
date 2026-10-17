# How to read `47_E8_simulation.json` — **it contains no ranking**

**Status: INSTRUMENT FAILURE RECORD, not a result.** Written 2026-09-24 by the
run's operator. This file is a companion to the artefact, added beside it rather
than inside it: the JSON is the record of what the run emitted and must not be
edited to say something the run did not say.

## 1. The headline

**Every half-life in this file is `None`, and every `boot_n` is `0`.**

    S1 large node, single layer    point=None  boot_n=0  CI=[None, None]
    S2 bridge node, single layer   point=None  boot_n=0  CI=[None, None]
    S3 large node, multi layer     point=None  boot_n=0  CI=[None, None]
    S4 bridge node, multi layer    point=None  boot_n=0  CI=[None, None]

There is **not one measurement** in the `ranking` array. It enumerates the four
scenarios and reports no value for any of them.

## 2. Why — the calibration did not fit, and could not have

    target_beta   = +2.442567567567567   (E3 design 'C activity + quality')
    achieved_beta = -1583.3279937322702
    residual      = 1585.7705612998377

The achieved β is **648x the target in magnitude and opposite in sign**. A
residual of this size is not a poor fit; it is a fit to a different quantity.
The ledger entry `C-110` (§ at `pipeline_reports/progress.md:1577`) diagnoses
the cause: **E3's outcome variable is the seller's weekly review count on
Apollon, while `simulate()` aggregates each seller's activity in its own
market.** The calibration therefore never contrasted the object E3 measured,
and **reporting a ranking from it would be a fabricated result.**

## 3. Three traps in this file's own field names

Anyone reading the JSON without the log will misread these three:

1. **`theta = 0.95` is the top edge of the search grid, not an optimum.**
   `calibrate()` scans `np.linspace(0.05, 0.95, 19)`. The best residual landed
   on the last point, so θ wants to go higher and the grid will not let it. A
   fit pinned to a boundary is the standard signature of **no interior
   solution** — the reported θ is an artefact of where the grid stops.
2. **`boot_n = 0` does NOT mean "no bootstrap was run".** The run's own header
   reads `Scenario ranking (6 bootstrap draws)`. `boot_n` is `len(v)` where `v`
   holds only draws that **yielded a usable half-life**. Six draws were run and
   all six failed. Read against the log line, the field name is backwards: it
   counts successes, not attempts. `0` is also the value most likely to be a
   sentinel, so this field is doubly unreadable on its own.
3. **`caveat` discusses policy choice, not the absence of a result.** It says
   the agent policy is stochastic and that prompt-driven is the plan's
   pre-registered degradation path. All true, and none of it alerts a reader
   that the run produced nothing. The `units` string
   (`half-life in weeks after the shock; larger = more damaging`) is likewise
   written as if values followed.

## 4. The only real numbers, and what they mean

The `final=0.093 / 0.091 / 0.060 / 0.062` in `47_E8_simulation.txt` are real:
each is `final_ratio`, the mean of the last four weeks over the mean of the
first ten. So the post-shock series ends at **6-9% of its pre-shock level**.
`halflife()` returning `None` here is **correct behaviour, not a crashed
metric** — its docstring reads "Weeks after the shock to regain 50% of
pre-shock activity. None if never," and recovery to 50% never occurs.

## 5. What would make this file readable

A rebuilt `simulate()` whose outcome is the same object E3 estimated (the
seller's weekly count on the shocked market, not the seller's own market). The
ledger records the planned reframe: change "bridge" from *bridge market* to
**multi-market seller** (`37_E3_bridge_probe.json`: 1353 of 6192 sellers are in
more than one market), which keeps the plan's question -- is it better to hit
connectors than hubs -- while giving it a base that exists in the data.

**Until then: cite this file as a failed calibration, never as an E8 result.**

## 6. A second, independent reason no ranking is possible here

Added 2026-09-24 after peer review. The calibration failure above is one reason
this run cannot rank. There is another, and **a better calibration would not
fix it**: the scenario axis is degenerate.

`47_E8_simulation.txt` records `scenarios (large=Apollon, bridge=Apollon)` --
the same market is both the "large node" and the "bridge node" -- and
`network.bridge` is `0.0` for every one of Apollon, CannaHome and Empire. So
S1 and S2 are not two treatments, and S3/S4 are the same three markets in a
different order. The plan's question (is it better to strike connectors than
hubs) cannot be asked of this network at all. The JSON's `ranking` array shows
this if read carefully -- S1 and S2 carry the identical `hits: ['Apollon']`.

This is why the §5 reframe matters twice over: moving "bridge" from *bridge
market* to **multi-market seller** is what gives the axis two genuinely
different arms, and it also restores the outcome variable E3 estimated.

**Keep three counts apart when citing this**: 1259 sellers in the simulated
network's pre-window, 6192 in E3's seller universe, 1353 of those in more than
one market. They are different denominators.
