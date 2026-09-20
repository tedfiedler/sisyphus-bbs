"""Balance simulator: plays whole climbs with the real rules.

    python -m lib.climb.sim            # summary over 300 seeded climbs
    python -m lib.climb.sim 100        # fewer, faster

The simulated climber is sensible but unimaginative: fights until hurt, heals
when it can pay, keeps its coin in the Vault, buys the best gear it can afford,
faces each gatekeeper once a day as soon as it has the XP, and goes for Ladon
only in tier-12 gear. It uses no calling skills, meets no events, and hears no
songs, so it is a conservative baseline: real play should be a little quicker.

``tests/test_climb_balance.py`` holds the median first ascent to about a month.
Change a constant in ``data.py``, run this, read the summary.
"""

import statistics
import sys
from dataclasses import dataclass, field
from random import Random

from lib.climb import data, rules
from lib.climb.rules import Outcome

HEAL_BELOW = 0.45          # heal when under this share of max HP...
REST_BELOW = 0.30          # ...and stop for the day if still under this
BAIL_BELOW = 0.25          # run from a creature when this hurt and it will not die next blow
READY_AT = 0.90            # face a gatekeeper only when nearly whole
MAX_DAYS = 400


@dataclass
class Report:
    days: int
    deaths: int = 0
    gate_failures: int = 0
    ladon_losses: int = 0
    reached: list[tuple[int, int]] = field(default_factory=list)      # (day, level)

    @property
    def finished(self) -> bool:
        return self.days < MAX_DAYS


def _spend_from_vault(c: rules.Climber, amount: int) -> None:
    if amount > c.purse:
        rules.apply_withdrawal(c, amount - c.purse)


def _shop(c: rules.Climber) -> None:
    for kind in ("weapon", "armour"):
        current = c.weapon if kind == "weapon" else c.armour
        for tier in range(min(data.LEVELS, c.level + 1), current, -1):
            cost = rules.gear_cost(c, kind, tier)
            if cost <= c.purse + c.vault:
                _spend_from_vault(c, cost)
                rules.apply_purchase(c, kind, tier)
                break


def _bank(c: rules.Climber) -> None:
    if c.purse:
        rules.apply_deposit(c, c.purse)


def _heal(c: rules.Climber) -> None:
    points = rules.affordable_healing(c, c.purse + c.vault)
    if points > 0:
        _spend_from_vault(c, rules.heal_cost(c, points))
        rules.apply_healing(c, points)


def _fight(rng: Random, c: rules.Climber, foe: rules.Foe) -> rules.Fight:
    fight = rules.open_fight(rng, c, foe)
    while fight.outcome is Outcome.ONGOING:
        hurt = c.hp < BAIL_BELOW * rules.max_hp(c)
        action = "run" if fight.can_run and hurt and fight.foe_hp > rules.attack_power(c) else "attack"
        rules.take_turn(rng, c, fight, action)
    return fight


def climb(rng: Random, ascents: int = 0, strength_gift: int = 0, defence_gift: int = 0) -> Report:
    """Play from the Foothills until Ladon falls (or MAX_DAYS pass)."""
    c = rules.new_climber(data.SPEAR)
    c.ascents, c.strength_gift, c.defence_gift = ascents, strength_gift, defence_gift
    report = Report(days=0)

    for day in range(1, MAX_DAYS + 1):
        report.days = day
        rules.apply_dawn(c)
        while c.alive and c.fights_left > 0:
            _shop(c)
            _bank(c)
            if c.hp < HEAL_BELOW * rules.max_hp(c):
                _heal(c)
                if c.hp < REST_BELOW * rules.max_hp(c):
                    break
            whole = c.hp >= READY_AT * rules.max_hp(c)

            if whole and rules.can_face_gatekeeper(c):
                c.gate_tried_today = True
                if _fight(rng, c, rules.gatekeeper(c.level, c.ascents)).outcome is Outcome.WON:
                    rules.apply_level_up(c)
                    report.reached.append((day, c.level))
                else:
                    report.gate_failures += 1
                continue

            geared = c.weapon == c.armour == data.LEVELS
            seasoned = c.xp >= data.REF_XP[-1] * data.SLOPE_FIGHTS_PER_DAY * 2
            if whole and geared and seasoned and rules.can_seek_ladon(c):
                c.gate_tried_today = True
                c.fights_left -= 1
                if _fight(rng, c, rules.ladon(c.ascents)).outcome is Outcome.WON:
                    return report
                report.ladon_losses += 1
                report.deaths += 1
                rules.apply_death(c)
                continue

            c.fights_left -= 1
            fight = _fight(rng, c, rules.random_creature(rng, c))
            if fight.outcome is Outcome.WON:
                rules.apply_victory(rng, c, fight)
            elif fight.outcome is Outcome.LOST:
                report.deaths += 1
                rules.apply_death(c)
    return report


def first_ascents(runs: int, seed: int = 0, **kwargs) -> list[Report]:
    return [climb(Random(seed + i), **kwargs) for i in range(runs)]


def win_rate(rng: Random, level: int, foe: rules.Foe, tiers_behind: int = 0, trials: int = 2000) -> float:
    """Share of fights a fresh climber of this level wins against *foe*."""
    wins = 0
    for _ in range(trials):
        c = rules.new_climber(data.SPEAR)
        c.level = level
        c.weapon = c.armour = max(1, level - tiers_behind)
        c.hp = rules.max_hp(c)
        fight = rules.open_fight(rng, c, foe)
        while fight.outcome is Outcome.ONGOING:
            rules.take_turn(rng, c, fight, "attack")
        wins += fight.outcome is Outcome.WON
    return wins / trials


def main(runs: int = 300) -> None:
    reports = first_ascents(runs)
    days = sorted(r.days for r in reports)
    decile = max(1, runs // 10)
    print(f"first ascent: median {statistics.median(days):.0f} days "
          f"(p10 {days[decile]}, p90 {days[-decile - 1]}), "
          f"{sum(not r.finished for r in reports)} of {runs} never finished")
    print(f"  deaths median {statistics.median(r.deaths for r in reports):.0f}, "
          f"failed gates median {statistics.median(r.gate_failures for r in reports):.0f}, "
          f"losses to Ladon mean {statistics.mean(r.ladon_losses for r in reports):.1f}")

    per_level: dict[int, list[int]] = {}
    for r in reports:
        previous = 0
        for day, level in r.reached:
            per_level.setdefault(level, []).append(day - previous)
            previous = day
    print("  median days to reach each level:",
          {level: statistics.median(v) for level, v in sorted(per_level.items())})

    veterans = first_ascents(max(50, runs // 2), seed=10_000, ascents=5, strength_gift=12, defence_gift=8)
    print(f"sixth ascent (creatures +15% health, a few seed gifts): "
          f"median {statistics.median(r.days for r in veterans):.0f} days")

    rng = Random(99)
    on_tier = [round(100 * win_rate(rng, lv, rules.gatekeeper(lv))) for lv in range(1, data.LEVELS)]
    behind = [round(100 * win_rate(rng, lv, rules.gatekeeper(lv), 1)) for lv in range(2, data.LEVELS)]
    print("gatekeeper win %, gear on tier:        ", on_tier)
    print("gatekeeper win %, one tier behind:     ", behind)
    print(f"Ladon win %, tier 12 / tier 11:         "
          f"{100 * win_rate(rng, 12, rules.ladon()):.0f} / {100 * win_rate(rng, 12, rules.ladon(), 1):.0f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
