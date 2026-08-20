#!/usr/bin/env python3
"""
The event registry.

Every module in the historical backtest used to carry its own copy of the
2025-12-04 event: epoch bounds, seed window, data-file dates, the EL income
share, even the axis labels. Adding a second event surfaced four separate
era-correctness bugs, each of which produced a plausible number rather than an
error:

  * the timely-target flag rule (EIP-7045 changed it at Deneb)
  * validator snapshots globbed with no date filter, so one era's effective
    balances and total_active_balance silently scored another era's epochs
  * `el_bonus.py` hardcoding December's total_active_balance and reading
    whatever MEV partitions happened to be on disk
  * two hardcoded seed windows and a stale flag-rule mirror inside the
    spec checker itself

An event is defined once, here, and every module reads from it. Adding a fourth
event should mean adding an entry, not editing modules.

Economic inputs (`el_bonus`, `eth_price`) are era-specific and are NOT
interchangeable between events. `el_bonus` sits in the denominator of
days-to-recoup, so absolute days are only comparable across events when the
denominators are. The vs-status-quo *ratios* are always comparable.
"""

from __future__ import annotations

from dataclasses import dataclass

# EIP-7045 (Deneb/Dencun) removed the inclusion-delay bound on timely target.
DENEB_EPOCH = 269_568


@dataclass(frozen=True)
class EventSpec:
    key: str
    title: str
    subtitle: str
    event_lo: int
    event_hi: int
    seed_lo: int
    seed_hi: int
    tail_hi: int
    pull_lo: int
    pull_hi: int
    derived_dir: str
    results_dir: str
    fig_prefix: str
    # Era-specific economics. Measured, not assumed -- see el_bonus.py.
    el_bonus: float
    eth_price: float
    total_active_balance_gwei: int
    mev_date_prefixes: tuple[str, ...]
    # Optional vertical marker on the trajectory figures (e.g. a fork).
    marker_epoch: int | None = None
    marker_label: str | None = None
    # How the seed window is described in prose (kept per-event so the
    # published December tables reproduce their original wording).
    seed_label: str = "baseline"
    # Published postmortem figures to cross-check the reconstruction
    # against, and the offline-share threshold that defines this
    # event's plateau. Both are event-specific.
    postmortem_note: str | None = None
    plateau_threshold: float = 0.20
    # Figure furniture. Kept per-event because an annotation naming one
    # event's numbers must never be painted onto another's chart.
    window_label: str | None = None          # x-axis label; defaults to subtitle
    h1_callout: tuple | None = None          # (text, xy, xytext)
    h1_note: tuple | None = None             # (text, x, y)
    h2_callout: tuple | None = None          # (text, xy, xytext)

    @property
    def pre_deneb(self) -> bool:
        return self.event_hi < DENEB_EPOCH

    @property
    def n_epochs(self) -> int:
        return self.event_hi - self.event_lo + 1

    @property
    def baseline_label(self) -> str:
        return f"{self.marker_label or 'PRE-EVENT'} BASELINE"


EVENTS: dict[str, EventSpec] = {
    # ---------------------------------------------------------------- Prysm
    # The published run. Values here reproduce results/ bit-for-bit; do not
    # change them without re-validating against the figures in the PR.
    "prysm": EventSpec(
        key="prysm",
        title="2025-12-04 post-Fusaka correlated outage",
        subtitle="2025-12-04 02:49:59Z → 07:18:47Z",
        event_lo=411_439,
        event_hi=411_480,
        seed_lo=411_200,
        seed_hi=411_391,
        tail_hi=411_700,
        pull_lo=411_200,
        pull_hi=411_700,
        derived_dir="data/derived",
        results_dir="results",
        fig_prefix="h",
        el_bonus=0.077,
        eth_price=3050.0,
        total_active_balance_gwei=35_632_266_500_000_000,
        mev_date_prefixes=("2025-11-", "2025-12-"),
        marker_epoch=411_392,
        marker_label="Fusaka activation",
        seed_label="pre-Fusaka",
        postmortem_note=("the postmortem reports a 74.7% participation floor, "
                         "~22.7% of the set offline, and an 18.5% missed-slot rate"),
        plateau_threshold=0.20,
        window_label="2025-12-04 02:49:59Z",
        h1_callout=(
            "97.8% of the non-attesting stake\nat the plateau missed both flags:\ndark, not slow",
            (1.6, 22.6), (3.3, 15.4),
        ),
        h1_note=(
            "a smaller cohort went dark at\nFusaka activation, five hours\n"
            "before the main event:\ntwo root causes, one trigger",
            -4.35, 5.0,
        ),
        h2_callout=("the first cohort alone already prices at ~8x", (-3.0, 8.0), (-5.9, 26)),
    ),
    # ---------------------------------------------------------------- Besu
    "besu": EventSpec(
        key="besu",
        title="2024-01-06 Besu mainnet halt",
        subtitle="2024-01-06 12:08Z → 2024-01-07 01:21Z",
        event_lo=254_470,
        event_hi=254_594,
        seed_lo=254_278,
        seed_hi=254_469,
        tail_hi=254_850,
        pull_lo=254_278,
        pull_hi=254_850,
        derived_dir="data/derived_besu",
        results_dir="results_besu",
        fig_prefix="besu",
        el_bonus=0.275,
        eth_price=2250.0,
        total_active_balance_gwei=28_915_761_000_000_000,
        mev_date_prefixes=("2023-12-", "2024-1-"),
        postmortem_note=("Lane B catalogued ~3.5% of validators affected over 13.3h; "
                         "no participation floor or missed-slot rate was published"),
        plateau_threshold=0.02,
    ),
    # ------------------------------------------------------------ May 2023
    # Two finality-loss incidents 21 hours apart (Prysm/Teku old-attestation
    # processing load). Both breached the mechanism's one-third saturation
    # point (participation floors 40% and 30.7%), and the pair is the only
    # real back-to-back test of re-arming between events. Pre-Deneb, so the
    # Altair timely-target rule applies (handled by the harness).
    #
    # el_bonus measured by el_bonus.py over 2023-04-20..05-13 relay payments:
    # 0.435 lower / 0.830 upper, 0.633 central. This window includes the early-
    # May 2023 memecoin MEV spike, which is also the era the event sat in.
    # total_active_balance confirmed from the era snapshot (18.13M ETH).
    "may2023": EventSpec(
        key="may2023",
        title="2023-05-11/12 mainnet finality incidents",
        subtitle="2023-05-11 20:06Z and 2023-05-12 17:20Z",
        event_lo=200_551,
        event_hi=200_760,
        seed_lo=200_359,
        seed_hi=200_550,
        tail_hi=201_000,
        pull_lo=200_359,
        pull_hi=201_000,
        derived_dir="data/derived_may2023",
        results_dir="results_may2023",
        fig_prefix="may",
        el_bonus=0.633,
        eth_price=1840.0,
        total_active_balance_gwei=18_130_000_000_000_000,
        mev_date_prefixes=("2023-4-", "2023-5-"),
        marker_epoch=200_750,
        marker_label="second incident",
        postmortem_note=("Prysm postmortem: finality lost epochs 200551-200554 "
                         "(participation floor ~40%) and 200750-200759 (floor 30.7%); "
                         "patches Prysm v4.0.3-hotfix / Teku 23.5.0 on May 13 ~03:45Z"),
        plateau_threshold=0.30,
    ),
    # ------------------------------------------------------------ Nethermind
    "nethermind": EventSpec(
        key="nethermind",
        title="2024-01-21 Nethermind consensus bug",
        subtitle="2024-01-21, bad block 19056922",
        event_lo=257_907,
        event_hi=257_943,
        seed_lo=257_715,
        seed_hi=257_906,
        tail_hi=258_200,
        pull_lo=257_715,
        pull_hi=258_200,
        derived_dir="data/derived_nethermind",
        results_dir="results_nethermind",
        fig_prefix="neth",
        # Measured by el_bonus.py over the event's own window; the
        # total_active_balance is read from the era's own snapshot.
        el_bonus=0.255,
        eth_price=2450.0,
        total_active_balance_gwei=28_971_000_000_000_000,
        mev_date_prefixes=("2024-1-",),
        postmortem_note=("Lane B catalogued ~8% of validators affected over 3.9h; "
                         "bad block 19056922"),
        plateau_threshold=0.04,
    ),
}


def get(key: str) -> EventSpec:
    try:
        return EVENTS[key]
    except KeyError:
        raise SystemExit(
            f"unknown event {key!r}; known events: {', '.join(sorted(EVENTS))}"
        ) from None


def add_event_arg(ap, default="prysm"):
    """Standard --event flag for every module in the harness."""
    ap.add_argument(
        "--event", default=default, choices=sorted(EVENTS),
        help="which event to operate on (see events.py)",
    )
    return ap
