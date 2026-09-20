"""The Long Climb: rules engine. Pure functions, scripted dice, exact outcomes."""

import pytest

from lib.climb import data, rules
from lib.climb.rules import Outcome


class Dice:
    """A stand-in for random.Random that returns what the test scripts.

    ``chance`` feeds ``random()``; ``rolls`` feeds ``randint()``. A roll may be
    "min" or "max" to take an end of whatever range the rules ask for, which
    keeps tests independent of the exact tables. Running dry is an error: a
    test must account for every roll the rules make.
    """

    def __init__(self, chance=(), rolls=()):
        self.chance, self.rolls = list(chance), list(rolls)
        self.ranges = []

    def random(self):
        return self.chance.pop(0)

    def randint(self, lo, hi):
        self.ranges.append((lo, hi))
        roll = self.rolls.pop(0)
        roll = {"min": lo, "max": hi}.get(roll, roll)
        assert lo <= roll <= hi, f"scripted roll {roll} outside {lo}..{hi}"
        return roll

    def spent(self):
        return not self.chance and not self.rolls


NO_AMBUSH, AMBUSH = 0.0, 0.99          # vs FIRST_STRIKE_CHANCE
NO_EVENT, AN_EVENT = 0.99, 0.0         # vs EVENT_CHANCE: the first roll of every "look for trouble"
PLAIN, MIGHTY = 0.99, 0.0              # vs MIGHTY_BLOW_CHANCE
ESCAPE, STUMBLE = 0.0, 0.99            # vs RUN_CHANCE


def climber(calling=data.SPEAR, **attrs):
    c = rules.new_climber(calling)
    for key, value in attrs.items():
        setattr(c, key, value)
    if "hp" not in attrs:
        c.hp = rules.max_hp(c)
    if "skill_left" not in attrs:
        c.skill_left = rules.skill_uses_per_day(c)
    return c


def dummy(hp=1000, attack=10, **kw):
    return rules.Foe(name="Training Post", hp=hp, attack=attack, **kw)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table", [
    data.MAX_HP, data.STRENGTH, data.DEFENCE, data.REF_XP, data.REF_DRACHMAE,
    data.XP_TO_NEXT, data.WEAPON_POWER, data.ARMOUR_POWER, data.WEAPON_PRICE, data.ARMOUR_PRICE,
])
def test_every_curve_rises(table):
    assert all(b > a for a, b in zip(table, table[1:]))


def test_prices_are_round_numbers_and_armour_is_cheaper():
    for price in data.WEAPON_PRICE + data.ARMOUR_PRICE:
        assert price == int(f"{price:.2g}".replace("e+", "e").split("e")[0].replace(".", "").ljust(len(str(price)), "0"))
    assert all(a < w for a, w in zip(data.ARMOUR_PRICE, data.WEAPON_PRICE))


def test_names_are_unique_and_complete():
    creatures = [name for band in data.CREATURES for name in band]
    assert len(creatures) == 96 == len(set(creatures))
    for names in (data.WEAPONS, data.ARMOURS, data.BANDS, data.GATEKEEPERS):
        assert len(set(names)) == len(names)
    assert len(data.GATEKEEPERS) == 11


def test_titles():
    assert [rules.title(n) for n in (0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 99)] == [
        "Climber", "Apple-Bearer", "Twice-Risen", "Thrice-Risen", "Thrice-Risen",
        "Stone-Roller", "Stone-Roller", "Friend of the Mountain", "Friend of the Mountain",
        "the Happy", "the Happy",
    ]


# ---------------------------------------------------------------------------
# The climber
# ---------------------------------------------------------------------------

def test_new_climber_starts_equipped_and_whole():
    c = rules.new_climber(data.TORCH)
    assert (c.level, c.weapon, c.armour, c.purse, c.vault) == (1, 1, 1, 60, 0)
    assert c.hp == rules.max_hp(c) == data.MAX_HP[0]
    assert c.fights_left == 15 and c.duels_left == 3 and c.skill_left == 1
    assert c.alive
    with pytest.raises(ValueError):
        rules.new_climber("bard")


def test_power_comes_from_level_gear_and_gifts():
    c = climber(level=5, weapon=6, armour=4, strength_gift=4, defence_gift=2, hp_gift=10)
    assert rules.attack_power(c) == data.STRENGTH[4] + 4 + data.WEAPON_POWER[5]
    assert rules.guard_power(c) == data.DEFENCE[4] + 2 + data.ARMOUR_POWER[3]
    assert rules.max_hp(c) == data.MAX_HP[4] + 10


def test_skill_uses_grow_with_rank():
    assert [rules.skill_uses_per_day(climber(rank=r)) for r in (0, 4, 5, 9, 10, 40)] == [1, 1, 2, 2, 3, 9]


def test_xp_to_next():
    assert rules.xp_to_next(1) == data.XP_TO_NEXT[0]
    assert rules.xp_to_next(11) == data.XP_TO_NEXT[10]
    assert rules.xp_to_next(12) is None


# ---------------------------------------------------------------------------
# Foes
# ---------------------------------------------------------------------------

def test_creatures_get_stronger_with_rank_and_band():
    band = [rules.creature(4, rank) for rank in range(1, 9)]
    assert [f.name for f in band] == list(data.CREATURES[3])
    for weaker, stronger in zip(band, band[1:]):
        assert stronger.hp > weaker.hp and stronger.attack >= weaker.attack
        assert stronger.xp > weaker.xp and stronger.drachmae > weaker.drachmae
    assert rules.creature(5, 1).hp > rules.creature(4, 1).hp
    for bad in ((0, 1), (13, 1), (1, 0), (1, 9)):
        with pytest.raises(ValueError):
            rules.creature(*bad)


def test_ascents_toughen_health_only_and_only_so_far():
    base, fifth, tenth, fiftieth = (rules.creature(6, 8, n) for n in (0, 5, 10, 50))
    assert fifth.hp == round(base.hp * 1.15) or abs(fifth.hp - base.hp * 1.15) <= 1
    assert tenth.hp == fiftieth.hp and tenth.hp > fifth.hp
    assert base.attack == fifth.attack == fiftieth.attack
    assert base.xp == fiftieth.xp and base.drachmae == fiftieth.drachmae


def test_random_creature_is_from_the_climbers_band():
    dice = Dice(rolls=[3])
    foe = rules.random_creature(dice, climber(level=7, ascents=2))
    assert foe.name == data.CREATURES[6][2] and dice.ranges == [(1, 8)]
    assert foe.hp == rules.creature(7, 3, 2).hp


def test_gatekeeper_and_ladon():
    strongest = rules.creature(3, 8)
    gate = rules.gatekeeper(3)
    assert gate.name == "Kleitos Two-Dogs" and gate.kind == rules.GATEKEEPER
    assert gate.hp == round(strongest.hp * 2.2) and gate.attack == round(strongest.attack * 1.3)
    assert gate.xp == gate.drachmae == 0
    for bad in (0, 12):
        with pytest.raises(ValueError):
            rules.gatekeeper(bad)

    boss = rules.ladon()
    assert boss.name == "Ladon" and boss.kind == rules.LADON
    assert boss.hp == round(data.MAX_HP[-1] * 2.8)
    assert rules.ladon(5).hp > boss.hp and rules.ladon(5).attack == boss.attack


def test_who_may_face_the_gatekeeper():
    c = climber(xp=data.XP_TO_NEXT[0])
    assert rules.can_face_gatekeeper(c)
    assert not rules.can_face_gatekeeper(climber(xp=data.XP_TO_NEXT[0] - 1))
    assert not rules.can_face_gatekeeper(climber(xp=10**9, gate_tried_today=True))
    assert not rules.can_face_gatekeeper(climber(xp=10**9, alive=False))
    assert not rules.can_face_gatekeeper(climber(level=12, xp=10**9))

    assert rules.can_seek_ladon(climber(level=12))
    assert not rules.can_seek_ladon(climber(level=11))
    assert not rules.can_seek_ladon(climber(level=12, fights_left=0))
    assert not rules.can_seek_ladon(climber(level=12, gate_tried_today=True))


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------

def test_opening_a_fight_without_ambush():
    c = climber()
    dice = Dice(chance=[NO_AMBUSH])
    fight = rules.open_fight(dice, c, dummy())
    assert fight.outcome is Outcome.ONGOING and fight.events == []
    assert c.hp == rules.max_hp(c) and fight.can_run and fight.lethal and dice.spent()


def test_ambush_lands_a_blow_first_but_never_on_the_sandal():
    c = climber()
    fight = rules.open_fight(Dice(chance=[AMBUSH], rolls=["max"]), c, dummy(attack=10))
    expected = 10 - rules.guard_power(c) // 2
    assert fight.events == [("ambush", 0), ("foe_hits", expected)]
    assert c.hp == rules.max_hp(c) - expected

    swift = climber(data.SANDAL)
    dice = Dice(chance=[AMBUSH])
    fight = rules.open_fight(dice, swift, dummy(attack=10))
    assert fight.events == [] and swift.hp == rules.max_hp(swift) and dice.spent()


def test_an_attack_round():
    c = climber(level=3, weapon=3)
    power = rules.attack_power(c)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(hp=500, attack=40))
    dice = Dice(chance=[PLAIN], rolls=["max", "min"])

    assert rules.take_turn(dice, c, fight, "attack") is Outcome.ONGOING
    assert dice.ranges == [(power // 2, power), (20, 40)]
    assert fight.foe_hp == 500 - power
    hurt = 20 - rules.guard_power(c) // 2
    assert fight.events == [("you_hit", power), ("foe_hits", hurt)]
    assert c.hp == rules.max_hp(c) - hurt


def test_mighty_blow_doubles():
    c = climber()
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy())
    rules.take_turn(Dice(chance=[MIGHTY], rolls=["max", "min"]), c, fight, "attack")
    assert fight.events[:2] == [("mighty", 0), ("you_hit", rules.attack_power(c) * 2)]


def test_armour_cannot_reduce_a_blow_below_one_and_guard_blunts_yours():
    tank = climber(level=12, armour=12)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), tank, dummy(attack=2))
    rules.take_turn(Dice(chance=[PLAIN], rolls=["min", "max"]), tank, fight, "attack")
    assert fight.events[-1] == ("foe_hits", 1)

    c = climber()
    rival = dummy(hp=100, kind=rules.CLIMBER, guard=8)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, rival)
    rules.take_turn(Dice(chance=[PLAIN], rolls=["max", "min"]), c, fight, "attack")
    assert fight.events[0] == ("you_hit", rules.attack_power(c) - 4)


def test_killing_blow_ends_the_fight_before_the_foe_replies():
    c = climber()
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(hp=1))
    dice = Dice(chance=[PLAIN], rolls=["min"])
    assert rules.take_turn(dice, c, fight, "attack") is Outcome.WON
    assert fight.foe_hp == 0 and fight.events[-1] == ("foe_falls", 0)
    assert c.hp == rules.max_hp(c) and dice.spent()
    assert rules.actions(c, fight) == ()
    with pytest.raises(ValueError):
        rules.take_turn(Dice(), c, fight, "attack")


def test_dying_to_a_creature_and_not_dying_to_a_gatekeeper():
    c = climber(hp=3)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(attack=500))
    assert rules.take_turn(Dice(chance=[PLAIN], rolls=["min", "max"]), c, fight, "attack") is Outcome.LOST
    assert c.hp == 0 and fight.events[-1] == ("you_fall", 0)

    c = climber(hp=3)
    gate = dummy(attack=500, kind=rules.GATEKEEPER)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, gate)
    assert not fight.lethal and not fight.can_run
    assert rules.take_turn(Dice(chance=[PLAIN], rolls=["min", "max"]), c, fight, "attack") is Outcome.LOST
    assert c.hp == 1


def test_running():
    c = climber()
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy())
    assert rules.take_turn(Dice(chance=[ESCAPE]), c, fight, "run") is Outcome.FLED
    assert c.hp == rules.max_hp(c)

    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(attack=10))
    assert rules.take_turn(Dice(chance=[STUMBLE], rolls=["max"]), c, fight, "run") is Outcome.ONGOING
    assert [e for e, _ in fight.events] == ["run_failed", "foe_hits"]


@pytest.mark.parametrize("kind", [rules.GATEKEEPER, rules.LADON])
def test_no_running_from_the_gate_or_the_garden(kind):
    c = climber(data.TORCH, rank=40)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(kind=kind))
    assert "run" not in rules.actions(c, fight) and "shadow" not in rules.actions(c, fight)
    with pytest.raises(ValueError):
        rules.take_turn(Dice(), c, fight, "run")


def test_only_offered_actions_are_accepted():
    c = climber(data.SPEAR)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy())
    assert rules.actions(c, fight) == ("attack", "fury", "run")
    for nonsense in ("flame", "mend", "buy", "", "ATTACK"):
        with pytest.raises(ValueError):
            rules.take_turn(Dice(), c, fight, nonsense)


# --- callings ---------------------------------------------------------------

def test_fury_triples_and_spends_a_use():
    c = climber(data.SPEAR, rank=5)
    assert c.skill_left == 2
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy())
    rules.take_turn(Dice(chance=[PLAIN], rolls=["max", "min"]), c, fight, "fury")
    assert fight.events[0] == ("fury", rules.attack_power(c) * 3) and c.skill_left == 1

    c.skill_left = 0
    assert rules.actions(c, fight) == ("attack", "run")
    with pytest.raises(ValueError):
        rules.take_turn(Dice(), c, fight, "fury")


def test_flame_doubles_and_scorches_exactly_one_blow():
    c = climber(data.TORCH, level=12, armour=1, hp=5000)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(hp=10**6, attack=400))
    guard = rules.guard_power(c) // 2

    rules.take_turn(Dice(chance=[PLAIN], rolls=["max", "max"]), c, fight, "flame")
    assert fight.events == [("flame", rules.attack_power(c) * 2), ("foe_hits", 200 - guard)]
    assert not fight.scorched

    rules.take_turn(Dice(chance=[PLAIN], rolls=["max", "max"]), c, fight, "attack")
    assert fight.events[-1] == ("foe_hits", 400 - guard)


def test_torch_learns_mend_then_shadow():
    assert rules.skills(climber(data.TORCH, rank=0)) == ("flame",)
    assert rules.skills(climber(data.TORCH, rank=10)) == ("flame", "mend")
    assert rules.skills(climber(data.TORCH, rank=20)) == ("flame", "mend", "shadow")

    c = climber(data.TORCH, rank=20, level=6, hp=10)
    fight = rules.open_fight(Dice(chance=[NO_AMBUSH]), c, dummy(attack=2))
    rules.take_turn(Dice(rolls=["min"]), c, fight, "mend")
    third = round(rules.max_hp(c) / 3)
    assert fight.events[0] == ("mend", third) and c.hp == 10 + third - 1

    c.hp = rules.max_hp(c) - 2
    rules.take_turn(Dice(rolls=["min"]), c, fight, "mend")
    assert fight.events[0] == ("mend", 2)                     # never past full

    assert rules.take_turn(Dice(), c, fight, "shadow") is Outcome.FLED
    assert fight.events == [("shadow", 0)]


def test_sandal_picks_a_pocket_once_and_never_trips_at_rank_ten():
    c = climber(data.SANDAL, rank=10)
    fight = rules.open_fight(Dice(chance=[AMBUSH]), c, dummy(hp=10**6, drachmae=200))
    rules.take_turn(Dice(chance=[PLAIN], rolls=["max", "min"]), c, fight, "quick_hands")
    assert fight.picked == 50
    assert "quick_hands" not in rules.actions(c, fight)

    dice = Dice()                                             # no chance roll at all
    assert rules.take_turn(dice, c, fight, "run") is Outcome.FLED

    novice = climber(data.SANDAL, rank=9)
    fight = rules.open_fight(Dice(chance=[AMBUSH]), novice, dummy(attack=4))
    assert rules.take_turn(Dice(chance=[STUMBLE], rolls=["min"]), novice, fight, "run") is Outcome.ONGOING


# ---------------------------------------------------------------------------
# After the fight
# ---------------------------------------------------------------------------

def _won(c, foe, picked=0):
    fight = rules.Fight(foe=foe, foe_hp=0, outcome=Outcome.WON, picked=picked)
    return fight


def test_victory_pays_out():
    c = climber(purse=10, xp=5)
    foe = rules.creature(1, 8)
    spoils = rules.apply_victory(Dice(chance=[0.99]), c, _won(c, foe, picked=7))
    assert (spoils.xp, spoils.drachmae, spoils.seed) == (foe.xp, foe.drachmae + 7, False)
    assert (c.xp, c.purse, c.seeds) == (5 + foe.xp, 10 + foe.drachmae + 7, 0)

    rules.apply_victory(Dice(chance=[0.0]), c, _won(c, foe))
    assert c.seeds == 1


def test_only_creatures_drop_seeds_and_only_wins_pay():
    c = climber()
    dice = Dice()
    rules.apply_victory(dice, c, _won(c, rules.gatekeeper(1)))
    assert c.seeds == 0 and dice.spent()
    with pytest.raises(ValueError):
        rules.apply_victory(Dice(), c, rules.Fight(foe=dummy(), foe_hp=5))


def test_death_takes_the_purse_and_a_tenth_of_xp_but_not_the_vault():
    c = climber(purse=340, vault=9000, xp=1005)
    assert rules.apply_death(c) == (340, 100)
    assert (c.purse, c.vault, c.xp, c.hp, c.alive) == (0, 9000, 905, 0, False)


def test_level_up():
    c = climber(level=3, xp=5000, rank=39, hp=1)
    rules.apply_level_up(c)
    assert (c.level, c.xp, c.rank) == (4, 0, 40) and c.hp == data.MAX_HP[3]
    rules.apply_level_up(c)
    assert c.rank == 40                                       # capped
    with pytest.raises(ValueError):
        rules.apply_level_up(climber(level=12))


def test_ascent_keeps_what_you_learned_and_takes_what_you_owned():
    c = climber(data.TORCH, level=12, xp=777, weapon=12, armour=12, purse=5000, vault=900_000,
                seeds=3, charm=14, rank=22, strength_gift=6, defence_gift=4, hp_gift=15, ascents=2)
    rules.apply_ascent(c)
    assert (c.ascents, c.calling, c.rank, c.charm, c.seeds) == (3, data.TORCH, 22, 14, 3)
    assert (c.strength_gift, c.defence_gift, c.hp_gift) == (6, 4, 15)
    assert (c.level, c.xp, c.weapon, c.armour) == (1, 0, 1, 1)
    assert (c.purse, c.vault) == (60, 0)
    assert c.hp == data.MAX_HP[0] + 15


def test_dawn():
    c = climber(level=4, rank=10, hp=0, alive=False, fights_left=0, duels_left=0, skill_left=0, gate_tried_today=True)
    rules.apply_dawn(c)
    assert c.alive and c.hp == data.MAX_HP[3]
    assert (c.fights_left, c.duels_left, c.skill_left, c.gate_tried_today) == (15, 3, 3, False)


# ---------------------------------------------------------------------------
# Town
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", range(1, 13))
def test_a_full_heal_costs_about_two_kills(level):
    c = climber(level=level, hp=0)
    full = rules.heal_cost(c, rules.max_hp(c))
    assert 1.6 <= full / data.REF_DRACHMAE[level - 1] <= 2.4


def test_healing():
    c = climber(level=2, hp=10, purse=1000)
    price = rules.heal_cost(c, 5)
    assert rules.apply_healing(c, 5) == price and c.hp == 15 and c.purse == 1000 - price

    assert rules.affordable_healing(c, 10**9) == rules.max_hp(c) - 15
    assert rules.affordable_healing(c, 0) == 0
    few = rules.affordable_healing(c, 7)
    assert rules.heal_cost(c, few) <= 7 < rules.heal_cost(c, few + 1)

    for bad in (0, -3, rules.max_hp(c)):
        with pytest.raises(ValueError):
            rules.apply_healing(c, bad)
    with pytest.raises(ValueError):
        rules.apply_healing(climber(hp=1, purse=0), 5)
    with pytest.raises(ValueError):
        rules.apply_healing(climber(hp=0, alive=False, purse=999), 5)


def test_buying_gear():
    c = climber(level=3, weapon=2, purse=10**6)
    assert rules.gear_cost(c, "weapon", 4) == data.WEAPON_PRICE[3] - data.WEAPON_PRICE[1] // 2
    assert rules.can_buy(c, "weapon", 3) and rules.can_buy(c, "weapon", 4)
    assert not rules.can_buy(c, "weapon", 5)                  # more than one tier above level
    assert not rules.can_buy(c, "weapon", 2) and not rules.can_buy(c, "weapon", 1)

    cost = rules.apply_purchase(c, "weapon", 4)
    assert c.weapon == 4 and c.purse == 10**6 - cost
    rules.apply_purchase(c, "armour", 2)
    assert c.armour == 2

    poor = climber(level=3, purse=rules.gear_cost(climber(level=3), "armour", 2) - 1)
    assert not rules.can_buy(poor, "armour", 2)
    with pytest.raises(ValueError):
        rules.apply_purchase(poor, "armour", 2)
    assert not rules.can_buy(climber(level=12, purse=10**9), "weapon", 13)
    assert not rules.can_buy(climber(purse=10**9, alive=False), "weapon", 2)
    for bad in (("helmet", 2), ("weapon", 0), ("weapon", 13)):
        with pytest.raises(ValueError):
            rules.gear_cost(c, *bad)


def test_the_vault():
    c = climber(purse=100, vault=0)
    rules.apply_deposit(c, 60)
    assert (c.purse, c.vault) == (40, 60)
    rules.apply_withdrawal(c, 10)
    assert (c.purse, c.vault) == (50, 50)
    for bad in (0, -5, 51):
        with pytest.raises(ValueError):
            rules.apply_deposit(c, bad)
        with pytest.raises(ValueError):
            rules.apply_withdrawal(c, bad)
    assert (c.purse, c.vault) == (50, 50)


def test_every_event_the_rules_can_report_has_words():
    """A missing line is a crash on the page, and only on the unlucky roll that reports it."""
    import inspect
    import re

    from lib.climb import text

    reported = set(re.findall(r'events\.append\(\("([a-z_]+)"', inspect.getsource(rules)))
    reported |= set(re.findall(r'event: str = "([a-z_]+)"', inspect.getsource(rules)))
    reported |= {"fury", "flame", "quick_hands"}              # passed to _you_strike by name
    assert reported and reported <= set(text.EVENTS), reported - set(text.EVENTS)
    for line in text.EVENTS.values():
        line.format(foe="Goat", n=3)                         # no stray placeholders
