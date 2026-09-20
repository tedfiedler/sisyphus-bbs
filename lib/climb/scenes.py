"""Which screen a player is on, what it offers, and what each choice does.

Two entry points: :func:`screen` describes the current scene, including every
action the player may take from it; :func:`act` performs one of those actions.
An action that is not on the current screen is refused, which is the whole of
the game's input validation: there is no way to ask for something the screen
did not offer.

Nothing here touches the database or the clock; the routes load a
:class:`~lib.climb.store.Player`, hand it over with a ``random.Random`` and
today's date, and save what comes back.
"""

from dataclasses import dataclass, field
from datetime import date
from random import Random

from lib.climb import data, rules, text
from lib.climb.rules import Outcome
from lib.climb.store import AGORA, Player

SLOPES, FIGHT, DEAD, HYGIEIA, VAULT = "slopes", "fight", "dead", "hygieia", "vault"
FORGE, AEGIS, PALAESTRA, ORCHARD = "forge", "aegis", "palaestra", "orchard"


class NotOffered(Exception):
    """The action is not available on the player's current screen."""


@dataclass
class Choice:
    key: str                    # hotkey, one letter
    label: str
    action: str
    amount: bool = False        # takes a number
    most: int = 0               # the largest sensible number, for the input's max


@dataclass
class Screen:
    heading: str
    lines: list[str]
    choices: list[Choice] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Creating a climber
# ---------------------------------------------------------------------------

def welcome() -> Screen:
    return Screen(
        heading=text.TITLE,
        lines=list(text.WELCOME) + [text.CALLINGS[key] for key in data.CALLINGS],
        choices=[
            Choice("s", "The (S)pear", f"begin:{data.SPEAR}"),
            Choice("t", "The (T)orch", f"begin:{data.TORCH}"),
            Choice("a", "The S(a)ndal", f"begin:{data.SANDAL}"),
        ],
    )


def begin(action: str) -> tuple[rules.Climber, list[str]]:
    """Create a climber from a ``begin:<calling>`` action."""
    calling = action.removeprefix("begin:")
    if not action.startswith("begin:") or calling not in data.CALLINGS:
        raise NotOffered(action)
    return rules.new_climber(calling), [text.BEGUN[calling]]


# ---------------------------------------------------------------------------
# Dawn
# ---------------------------------------------------------------------------

def dawn(player: Player, today: date) -> bool:
    """Bring the player up to today. Returns True if a new day began for them."""
    if player.last_day is not None and player.last_day >= today:
        return False
    was_dead = not player.climber.alive
    mid_fight = player.fight is not None
    rules.apply_dawn(player.climber)
    player.fight = None
    player.scene = AGORA
    player.last_day = today
    player.notice = [text.DAWN_AFTER_DEATH if was_dead else text.DAWN]
    if mid_fight and not was_dead:
        player.notice.append(text.DAWN_MID_FIGHT)
    return True


# ---------------------------------------------------------------------------
# Describing the current scene
# ---------------------------------------------------------------------------

_SKILL_LABELS = {
    "fury": ("f", "(F)ury"), "flame": ("f", "(F)lame"), "mend": ("m", "(M)end"),
    "shadow": ("s", "(S)hadow"), "quick_hands": ("q", "(Q)uick Hands"),
}


def screen(player: Player) -> Screen:
    c = player.climber
    if not c.alive:
        return Screen("Dead until dawn", list(text.DEAD))

    if player.scene == FIGHT and player.fight is not None:
        fight = player.fight
        choices = []
        for action in rules.actions(c, fight):
            if action == "attack":
                choices.append(Choice("a", "(A)ttack", "fight:attack"))
            elif action == "run":
                choices.append(Choice("r", "(R)un", "fight:run"))
            else:
                key, label = _SKILL_LABELS[action]
                choices.append(Choice(key, f"{label} [{c.skill_left} left]", f"fight:{action}"))
        return Screen(fight.foe.name, [f"{fight.foe.name}: {fight.foe_hp} hit points."], choices)

    if player.scene == SLOPES:
        band = data.BANDS[c.level - 1]
        lines = [text.SLOPES.format(band=band)]
        choices = []
        if c.fights_left > 0:
            choices.append(Choice("l", "(L)ook for trouble", "seek"))
        else:
            lines.append(text.SLOPES_SPENT)
        choices.append(Choice("b", "(B)ack to town", f"go:{AGORA}"))
        return Screen(band, lines, choices)

    if player.scene == HYGIEIA:
        missing = rules.max_hp(c) - c.hp
        lines = list(text.HYGIEIA)
        choices = []
        if missing == 0:
            lines.append(text.HYGIEIA_WHOLE)
        else:
            lines.append(text.HYGIEIA_PRICE.format(price=rules.heal_price_per_point(c.level), missing=missing))
            can_afford = rules.affordable_healing(c, c.purse)
            if can_afford > 0:
                label = "(H)eal fully" if can_afford == missing else f"(H)eal all you can afford ({can_afford})"
                choices.append(Choice("h", label, "heal:all"))
                choices.append(Choice("p", "Heal some (p)oints", "heal:some", amount=True, most=can_afford))
        choices.append(Choice("b", "(B)ack to the Agora", f"go:{AGORA}"))
        return Screen("House of Hygieia", lines, choices)

    if player.scene == VAULT:
        choices = []
        if c.purse > 0:
            choices.append(Choice("d", f"(D)eposit everything ({c.purse})", "vault:deposit_all"))
            choices.append(Choice("s", "Deposit (s)ome", "vault:deposit", amount=True, most=c.purse))
        if c.vault > 0:
            choices.append(Choice("w", f"(W)ithdraw everything ({c.vault})", "vault:withdraw_all"))
            choices.append(Choice("t", "Wi(t)hdraw some", "vault:withdraw", amount=True, most=c.vault))
        choices.append(Choice("b", "(B)ack to the Agora", f"go:{AGORA}"))
        return Screen("The Ferryman's Vault", list(text.VAULT), choices)

    if player.scene in (FORGE, AEGIS):
        return _shop(c, "weapon" if player.scene == FORGE else "armour")

    if player.scene == ORCHARD:
        lines = list(text.ORCHARD) + [text.ORCHARD_SEEDS.format(seeds=_seeds(c.seeds))]
        choices = []
        if rules.can_take_gift(c):
            choices = [
                Choice("s", f"(S)trength +{data.GIFTS['strength']}", "gift:strength"),
                Choice("d", f"(D)efence +{data.GIFTS['defence']}", "gift:defence"),
                Choice("v", f"(V)igour: max hit points +{data.GIFTS['vigour']}", "gift:vigour"),
            ]
        else:
            lines.append(text.ORCHARD_POOR)
        choices.append(Choice("b", "(B)ack to the Agora", f"go:{AGORA}"))
        return Screen("The Orchard Gate", lines, choices)

    if player.scene == PALAESTRA:
        lines = list(text.PALAESTRA)
        choices = []
        needed = rules.xp_to_next(c.level)
        if needed is None:
            lines.append(text.GATE_TOP)
        else:
            name = data.GATEKEEPERS[c.level - 1]
            lines.append(text.GATE_AHEAD.format(band=data.BANDS[c.level - 1], name=name))
            if c.gate_tried_today:
                lines.append(text.GATE_TRIED)
            elif rules.can_face_gatekeeper(c):
                lines.append(text.GATE_READY)
                choices.append(Choice("f", f"(F)ace {name}", "gate"))
            else:
                lines.append(text.GATE_NOT_READY.format(xp=c.xp, needed=needed))
        choices.append(Choice("b", "(B)ack to the Agora", f"go:{AGORA}"))
        return Screen("The Palaestra", lines, choices)

    lines = list(text.AGORA)
    if c.fights_left == 0:
        lines.append(text.AGORA_SPENT)
    return Screen("The Agora", lines, [
        Choice("c", "(C)limb the Slopes", f"go:{SLOPES}"),
        Choice("f", "Brontes' (F)orge", f"go:{FORGE}"),
        Choice("a", "(A)egis Row", f"go:{AEGIS}"),
        Choice("h", "House of (H)ygieia", f"go:{HYGIEIA}"),
        Choice("v", "The Ferryman's (V)ault", f"go:{VAULT}"),
        Choice("p", "The (P)alaestra", f"go:{PALAESTRA}"),
        Choice("o", "The (O)rchard Gate", f"go:{ORCHARD}"),
    ])


def _seeds(n: int) -> str:
    return "one seed" if n == 1 else f"{n} seeds" if n else "no seeds"


def _shop(c: rules.Climber, kind: str) -> Screen:
    """A shop lists what it would sell you; only what you can pay for is a button."""
    names = data.WEAPONS if kind == "weapon" else data.ARMOURS
    carried = c.weapon if kind == "weapon" else c.armour
    lines = list(text.FORGE if kind == "weapon" else text.AEGIS_ROW)
    lines.append(text.CARRYING.format(item=names[carried - 1]))
    choices = []
    offers = rules.gear_on_offer(c, kind)
    for number, (tier, price, affordable) in enumerate(offers, start=1):
        item = names[tier - 1]
        if affordable:
            lines.append(text.ON_OFFER.format(item=item, price=price))
            choices.append(Choice(str(number), f"({number}) Buy the {item}", f"buy:{kind}:{tier}"))
        else:
            lines.append(text.TOO_DEAR.format(item=item, price=price, purse=c.purse))
    if not offers:
        lines.append(text.BEST_THERE_IS if carried == data.LEVELS else text.NOTHING_BETTER)
    choices.append(Choice("b", "(B)ack to the Agora", f"go:{AGORA}"))
    return Screen("Brontes' Forge" if kind == "weapon" else "Aegis Row", lines, choices)


def status(player: Player) -> dict:
    """The line of numbers shown on every screen."""
    c = player.climber
    return {
        "level": c.level,
        "band": data.BANDS[c.level - 1],
        "title": rules.title(c.ascents),
        "calling": data.CALLINGS[c.calling][0],
        "hp": c.hp, "max_hp": rules.max_hp(c),
        "purse": c.purse, "vault": c.vault,
        "xp": c.xp, "xp_needed": rules.xp_to_next(c.level),
        "fights_left": c.fights_left,
        "weapon": data.WEAPONS[c.weapon - 1], "armour": data.ARMOURS[c.armour - 1],
        "seeds": c.seeds,
    }


# ---------------------------------------------------------------------------
# Acting
# ---------------------------------------------------------------------------

def _narrate(fight: rules.Fight) -> list[str]:
    return [text.EVENTS[event].format(foe=fight.foe.name, n=n) for event, n in fight.events]


def _after_blows(rng: Random, player: Player) -> None:
    """Settle a fight that has just ended, if it has."""
    c, fight = player.climber, player.fight
    if fight.outcome is Outcome.ONGOING:
        return
    player.fight = None
    if fight.foe.kind == rules.GATEKEEPER:
        _, won, lost = text.GATEKEEPERS[c.level - 1]
        if fight.outcome is Outcome.WON:
            rules.apply_level_up(c)
            player.notice += [won, text.LEVEL_UP.format(band=data.BANDS[c.level - 1], level=c.level)]
        else:
            player.notice.append(lost)
        player.scene = PALAESTRA
        return
    if fight.outcome is Outcome.WON:
        spoils = rules.apply_victory(rng, c, fight)
        player.notice.append(text.SPOILS.format(drachmae=spoils.drachmae, xp=spoils.xp))
        if spoils.seed:
            player.notice.append(text.SEED)
        if rules.can_face_gatekeeper(c):
            player.notice.append(text.READY_FOR_GATE)
        player.scene = SLOPES
    elif fight.outcome is Outcome.FLED:
        player.scene = SLOPES
    else:
        drachmae, xp = rules.apply_death(c)
        player.notice += [line.format(drachmae=drachmae, xp=xp) for line in text.DEATH]
        player.scene = DEAD


def act(rng: Random, player: Player, action: str, amount: int = 0) -> None:
    """Perform one action from the player's current screen, or raise NotOffered."""
    offered = {choice.action: choice for choice in screen(player).choices}
    if action not in offered:
        raise NotOffered(action)
    c = player.climber
    player.notice = []

    if action.startswith("go:"):
        player.scene = action.removeprefix("go:")

    elif action == "seek":
        c.fights_left -= 1
        player.fight = rules.open_fight(rng, c, rules.random_creature(rng, c))
        player.scene = FIGHT
        player.notice.append(text.FIGHT_OPENS.format(foe=player.fight.foe.name))
        player.notice += _narrate(player.fight)
        _after_blows(rng, player)

    elif action.startswith("fight:"):
        rules.take_turn(rng, c, player.fight, action.removeprefix("fight:"))
        player.notice += _narrate(player.fight)
        _after_blows(rng, player)

    elif action == "gate":
        c.gate_tried_today = True
        level = c.level
        player.fight = rules.open_fight(rng, c, rules.gatekeeper(level, c.ascents))
        player.scene = FIGHT
        player.notice.append(text.GATE_OPENS.format(band=data.BANDS[level - 1], name=data.GATEKEEPERS[level - 1]))
        player.notice.append(text.GATEKEEPERS[level - 1][0])
        player.notice += _narrate(player.fight)
        _after_blows(rng, player)

    elif action.startswith("buy:"):
        _, kind, tier = action.split(":")
        names = data.WEAPONS if kind == "weapon" else data.ARMOURS
        cost = rules.apply_purchase(c, kind, int(tier))
        bought = text.BOUGHT_WEAPON if kind == "weapon" else text.BOUGHT_ARMOUR
        player.notice.append(bought.format(cost=cost, item=names[int(tier) - 1]))

    elif action.startswith("gift:"):
        gift = action.removeprefix("gift:")
        player.notice.append(text.GIFTS[gift].format(n=rules.apply_gift(c, gift)))

    elif action in ("heal:all", "heal:some"):
        points = rules.affordable_healing(c, c.purse) if action == "heal:all" else amount
        try:
            cost = rules.apply_healing(c, points)
            player.notice.append(text.HEALED.format(points=points, cost=cost))
        except ValueError:
            player.notice.append(text.HEAL_REFUSED)

    elif action.startswith("vault:"):
        deposit = "deposit" in action
        if action.endswith("_all"):
            amount = c.purse if deposit else c.vault
        try:
            (rules.apply_deposit if deposit else rules.apply_withdrawal)(c, amount)
            player.notice.append((text.DEPOSITED if deposit else text.WITHDRAWN).format(amount=amount))
        except ValueError:
            player.notice.append(text.VAULT_REFUSED)
