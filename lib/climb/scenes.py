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
from lib.content_filter import contains_url
from lib.climb.rules import Outcome
from lib.climb.store import AGORA, Player

SLOPES, FIGHT, DEAD, HYGIEIA, VAULT = "slopes", "fight", "dead", "hygieia", "vault"
FORGE, AEGIS, PALAESTRA, ORCHARD = "forge", "aegis", "palaestra", "orchard"
SUMMIT, STELE = "summit", "stele"
LETHE, WALL, HERALD = "lethe", "wall", "herald"
EVENT, FIRE = "event", "fire"
CAMP, OTHERS = "camp", "others"
CORNER, HEARTS, SUITOR = "corner", "hearts", "suitor"

# What a player's `happenings` may contain, for the route to act on: each is
# (kind, detail). The first four are news; WROTE carries a line for the wall.
ARRIVED, LEVEL_GAINED, DIED, ASCENDED, WROTE = "arrival", "level", "death", "ascent", "wall"
KID_HOME = "kid"
# Robbery. ATTEMPTED's detail is the victim's id; the other two carry a dict
# (victim id and name, and for FELL_TO the purse the robber dropped), because
# the route has to settle them against the victim's own row.
ATTEMPTED, ROBBED, FELL_TO = "attempted", "robbed", "fell_to"


# Courtship. WED_REGULAR's detail is the regular's name; the rest carry
# {"id", "name"} for the route to settle against the other climber's row.
WED_REGULAR = "wed_regular"
FLIRT, PROPOSE, ACCEPT, DECLINE, DIVORCE = "flirt", "propose", "accept", "decline", "divorce"
SHUT_DOOR, OPEN_DOOR = "shut_door", "open_door"


@dataclass
class Person:
    """Another climber as the hearts screens see them, prepared by the route."""

    user_id: int
    name: str
    title: str
    band: str
    open_heart: bool
    free: bool                      # not married to anyone
    affinity: int = 0
    flirted_with_me: bool = False
    proposal: str = ""              # "", "from_them", or "from_me"
    spouse: bool = False
    door_shut: bool = False         # by me, to them


@dataclass
class Target:
    """A sleeper the Camp screen offers, as prepared by the route."""

    user_id: int
    name: str
    foe: rules.Foe
    title: str
    weapon: str
    armour: str
    in_room: bool


class NotOffered(Exception):
    """The action is not available on the player's current screen."""


@dataclass
class Choice:
    key: str                    # hotkey, one letter
    label: str
    action: str
    amount: bool = False        # takes a number
    most: int = 0               # the largest sensible number, for the input's max
    words: bool = False         # takes a line of text


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

def dawn(player: Player, today: date, spouse: str = "", spouse_played_yesterday: bool = False) -> bool:
    """Bring the player up to today. Returns True if a new day began for them.

    *spouse* is the name of the climber they are married to, if any, and
    *spouse_played_yesterday* whether that climber was on the mountain; the
    route supplies both, since they live in somebody else's row.
    """
    if player.last_day is not None and player.last_day >= today:
        return False
    was_dead = not player.climber.alive
    mid_fight = player.fight is not None
    rules.apply_dawn(player.climber)
    player.fight = None
    player.event = None
    player.scene = AGORA
    player.last_day = today
    player.notice = [text.DAWN_AFTER_DEATH if was_dead else text.DAWN]
    if mid_fight and not was_dead:
        player.notice.append(text.DAWN_MID_FIGHT)
    brought = rules.apply_spouse_dawn(player.climber, spouse_played_yesterday)
    if brought:
        kind, n = brought
        name = text.REGULAR_NAMES.get(rules.courting(player.climber) or "", spouse)
        player.notice.append((text.SPOUSE_GIFT if kind == "gift" else text.SPOUSE_FIGHTS).format(name=name, n=n))
    return True


# ---------------------------------------------------------------------------
# Describing the current scene
# ---------------------------------------------------------------------------

_CALLING_CHOICES = {
    data.SPEAR: ("s", "the (S)pear"), data.TORCH: ("t", "the (T)orch"), data.SANDAL: ("a", "the S(a)ndal"),
}

_SKILL_LABELS = {
    "fury": ("f", "(F)ury"), "flame": ("f", "(F)lame"), "mend": ("m", "(M)end"),
    "shadow": ("s", "(S)hadow"), "quick_hands": ("q", "(Q)uick Hands"),
}


def _suitor(player: Player, people: list[Person] | None) -> Person | None:
    return next((p for p in people or [] if str(p.user_id) == player.event), None)


def _corner(c: rules.Climber) -> Screen:
    lines = list(text.CORNER)
    choices = []
    current = rules.courting(c)
    if c.wed and current:
        lines.append(text.COURT_WED.format(name=text.REGULAR_NAMES[current]))
    elif current:
        step = c.courtship + 1
        done = text.COURT_STEPS[c.courtship - 1] if c.courtship else "a promising start"
        lines.append(text.COURT_STATUS.format(
            name=text.REGULAR_NAMES[current], done=done,
            next=text.COURT_STEPS[step - 1], need=data.COURTSHIP_CHARM[step - 1]))
    elif not c.heart:
        lines.append(text.COURT_FRESH)

    reasons = set()
    for key, regular in (("k", "kalliste"), ("t", "theron")):
        name = text.REGULAR_NAMES[regular]
        reason = rules.why_not_court(c, regular)
        if reason is None:
            step = text.COURT_STEPS[c.courtship if current == regular else 0]
            label = f"({key.upper()}){name[1:]}: {step}"
            choices.append(Choice(key, label, f"court:{regular}"))
        elif current in (None, regular):
            reasons.add(reason)
        elif reason == "other" and not c.wed:
            lines.append(text.COURT_OTHER.format(name=name, other=text.REGULAR_NAMES[current]))
    step = c.courtship + 1 if current else 1
    if "charm" in reasons:
        lines.append(text.COURT_NEED_CHARM.format(
            next=text.COURT_STEPS[step - 1], need=data.COURTSHIP_CHARM[step - 1], charm=c.charm))
    if "gift" in reasons:
        lines.append(text.COURT_NEED_GIFT.format(price=rules.gift_price(c)))
    if "today" in reasons and c.alive:
        lines.append(text.COURT_TOMORROW)
    if "taken" in reasons:
        lines.append(text.COURT_TAKEN)

    if current:
        choices.append(Choice("l", f"(L)eave {text.REGULAR_NAMES[current]}", "part"))
    choices.append(Choice("h", "Other climbers' (h)earts", f"go:{HEARTS}"))
    choices.append(Choice("b", "(B)ack to the bar", f"go:{LETHE}"))
    return Screen("The corner table", lines, choices)


def _hearts(c: rules.Climber, people: list[Person]) -> Screen:
    lines = list(text.HEARTS)
    lines.append(text.HEART_OPEN if c.open_heart else text.HEART_CLOSED)
    choices = []
    if not people and c.open_heart:
        lines.append(text.NOBODY_OPEN)
    for number, person in enumerate(people, start=1):
        note = (
            "spouse" if person.spouse else
            "proposed_to_you" if person.proposal == "from_them" else
            "you_proposed" if person.proposal == "from_me" else
            "flirted" if person.flirted_with_me else ""
        )
        lines.append(f"({number}) " + text.PERSON.format(name=person.name, title=person.title, band=person.band)
                     + text.PERSON_NOTE.get(note, ""))
        choices.append(Choice(str(number), f"({number}) {person.name}", f"suitor:{person.user_id}"))
    if c.open_heart:
        choices.append(Choice("c", "(C)lose your heart to other climbers", "heart:close"))
    else:
        choices.append(Choice("o", "(O)pen your heart to other climbers", "heart:open"))
    choices.append(Choice("b", "(B)ack to the corner table", f"go:{CORNER}"))
    return Screen("Hearts", lines, choices)


def _suitor_screen(c: rules.Climber, person: Person) -> Screen:
    lines = [text.PERSON.format(name=person.name, title=person.title, band=person.band)]
    choices = []
    if person.spouse:
        lines.append(text.PERSON_NOTE["spouse"].strip())
        choices.append(Choice("e", "(E)nd the marriage", "divorce"))
    else:
        lines.append(text.SUITOR_AFFINITY.format(
            name=person.name, affinity=person.affinity, needed=data.AFFINITY_TO_PROPOSE))
        if person.proposal == "from_them":
            lines.append(text.PERSON_NOTE["proposed_to_you"].strip())
            if not c.wed and person.free:
                choices.append(Choice("y", "Say (y)es", "accept"))
            choices.append(Choice("n", "Say (n)o", "decline"))
        elif person.proposal == "from_me":
            lines.append(text.PERSON_NOTE["you_proposed"].strip())
        elif person.flirted_with_me:
            lines.append(text.PERSON_NOTE["flirted"].strip())
        if not person.door_shut and rules.why_not_flirt(c, person.open_heart) is None:
            choices.append(Choice("f", "(F)lirt", "flirt"))
        if not person.proposal and not person.door_shut and person.open_heart \
                and rules.can_propose(c, person.affinity, person.free):
            choices.append(Choice("p", "(P)ropose", "propose"))
        if person.door_shut:
            choices.append(Choice("o", "(O)pen the door to them again", "door:open"))
        else:
            choices.append(Choice("c", "(C)lose the door on them, silently", "door:shut"))
    choices.append(Choice("b", "(B)ack", f"go:{HEARTS}"))
    return Screen(person.name, lines, choices)


def screen(player: Player, camp: list[Target] | None = None, people: list[Person] | None = None) -> Screen:
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
        if fight.foe.kind == rules.LADON:
            heads = rules.heads_left(fight)
            line = text.LADON_ONE_HEAD if heads == 1 else text.LADON_HEADS.format(heads=heads)
        else:
            line = f"{fight.foe.name}: {fight.foe_hp} hit points."
        return Screen(fight.foe.name, [line], choices)

    if player.scene == EVENT and player.event:
        kind = player.event
        lines = list(text.EVENT_INTRO[kind])
        choices = []
        for option in rules.event_options(c, kind):
            key, label = text.EVENT_OPTIONS[kind][option]
            if option == "wager":
                most = rules.satyr_max_stake(c)
                lines.append(text.SATYR_STAKE.format(most=most))
                choices.append(Choice(key, label, f"event:{option}", amount=True, most=most))
            else:
                choices.append(Choice(key, label, f"event:{option}"))
        return Screen("On the path", lines, choices)

    if player.scene == FIRE:
        lines = list(text.FIRE)
        choices = []
        most = rules.knucklebones_max_stake(c)
        if most > 0:
            left = data.KNUCKLEBONES_PER_DAY - c.knucklebones_today
            lines.append(text.FIRE_GAMES.format(most=most, left=left))
            choices.append(Choice("k", "(K)nucklebones", "knucklebones", amount=True, most=most))
        else:
            lines.append(text.FIRE_NO_GAMES)
        for calling, (key, label) in _CALLING_CHOICES.items():
            if calling != c.calling:
                choices.append(Choice(key, f"Take up {label}", f"calling:{calling}"))
        choices.append(Choice("o", "Ask about the (o)thers", f"go:{OTHERS}"))
        choices.append(Choice("b", "(B)ack to the Slopes", f"go:{SLOPES}"))
        return Screen("The Shepherds' Fire", lines, choices)

    if player.scene == CORNER:
        return _corner(c)

    if player.scene == SUITOR and _suitor(player, people) is not None:
        return _suitor_screen(c, _suitor(player, people))

    if player.scene in (HEARTS, SUITOR):        # a suitor who has gone falls back to the list
        return _hearts(c, people or [])

    if player.scene == CAMP:
        lines = list(text.CAMP)
        choices = []
        if c.key:
            lines.append(text.CAMP_KEY)
        if c.duels_left < 1:
            lines.append(text.CAMP_SPENT)
        elif not camp:
            lines.append(text.CAMP_EMPTY)
        else:
            for number, target in enumerate(camp, start=1):
                line = text.SLEEPER_ROOM if target.in_room else text.SLEEPER
                lines.append(f"({number}) " + line.format(
                    name=target.name, title=target.title, weapon=target.weapon, armour=target.armour))
                choices.append(Choice(str(number), f"({number}) Rob {target.name}", f"rob:{target.user_id}"))
        choices.append(Choice("b", "(B)ack to the Agora", f"go:{AGORA}"))
        return Screen(f"The Camp ({c.duels_left} left tonight)", lines, choices)

    if player.scene == OTHERS:
        return Screen("Around the fire", list(text.OTHERS), [Choice("b", "(B)ack to the fire", f"go:{FIRE}")])

    if player.scene == SUMMIT:
        return Screen("The Garden", [text.SUMMIT_REST], [Choice("d", "(D)own to the Agora", f"go:{AGORA}")])

    if player.scene == STELE:
        return Screen("The Stele", list(text.STELE), [Choice("b", "(B)ack to the Agora", f"go:{AGORA}")])

    if player.scene == HERALD:
        return Screen("The Herald's Board", list(text.HERALD), [Choice("b", "(B)ack to the Agora", f"go:{AGORA}")])

    if player.scene == WALL:
        lines, choices = [text.WALL], []
        if c.wall_today < data.WALL_LINES_PER_DAY:
            choices.append(Choice("s", "(S)cratch a line", "wall:write", words=True))
        else:
            lines.append(text.WALL_FULL)
        choices.append(Choice("b", "(B)ack to the bar", f"go:{LETHE}"))
        return Screen("The Wall", lines, choices)

    if player.scene == LETHE:
        lines = list(text.LETHE)
        choices = []
        if c.sung_today:
            lines.append(text.ORPHEUS_DONE)
        else:
            choices.append(Choice("o", "Ask (O)rpheus for a song", "song"))
        choices.append(Choice("w", "Read the (W)all", f"go:{WALL}"))
        if c.room:
            lines.append(text.LETHE_ROOMED)
        else:
            lines.append(text.ROOM_OFFER.format(price=rules.room_price(c)))
            if c.purse >= rules.room_price(c):
                choices.append(Choice("r", "Take a (R)oom for the night", "room"))
        if c.purse >= rules.wine_price(c):
            choices.append(Choice("c", f"A (C)up of wine ({rules.wine_price(c)} dr)", "wine"))
        choices.append(Choice("t", "Join the corner (t)able", f"go:{CORNER}"))
        if not c.key:
            lines.append(text.KEY_OFFER.format(price=rules.key_price(c)))
            if c.purse >= rules.key_price(c):
                choices.append(Choice("k", "A quiet word about a (k)ey", "key"))
        choices.append(Choice("b", "(B)ack to the Agora", f"go:{AGORA}"))
        return Screen("The Lethe House", lines, choices)

    if player.scene == SLOPES:
        band = data.BANDS[c.level - 1]
        lines = [text.SLOPES.format(band=band)]
        choices = []
        if c.fights_left > 0:
            choices.append(Choice("l", "(L)ook for trouble", "seek"))
        else:
            lines.append(text.SLOPES_SPENT)
        if c.fire_known:
            choices.append(Choice("f", "The Shepherds' (F)ire", f"go:{FIRE}"))
        if c.level == data.LEVELS:
            if rules.can_seek_ladon(c):
                choices.append(Choice("s", "(S)eek the Garden", "garden"))
            elif c.gate_tried_today:
                lines.append(text.GARDEN_TRIED)
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
        Choice("l", "The (L)ethe House", f"go:{LETHE}"),
        Choice("p", "The (P)alaestra", f"go:{PALAESTRA}"),
        Choice("o", "The (O)rchard Gate", f"go:{ORCHARD}"),
        Choice("m", "The Ca(m)p, after dark", f"go:{CAMP}"),
        Choice("n", "(N)ews from the Herald", f"go:{HERALD}"),
        Choice("s", "The (S)tele", f"go:{STELE}"),
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

def with_article(foe: rules.Foe) -> str:
    """The foe as it reads mid-sentence: creatures take "the", people do not."""
    name = foe.name
    if foe.kind != rules.CREATURE or name in data.NO_ARTICLE_FOES:
        return "the Warden" if name == "The Warden" else name
    return "the " + name.removeprefix("The ")


def _narrate(fight: rules.Fight) -> list[str]:
    foe = with_article(fight.foe)
    plural = fight.foe.name in data.PLURAL_FOES
    words = {
        "foe": foe, "Foe": foe[0].upper() + foe[1:],
        "hits": "hit" if plural else "hits", "is": "are" if plural else "is",
    }
    return [text.EVENTS[event].format(n=n, **words) for event, n in fight.events]


def _after_blows(rng: Random, player: Player) -> None:
    """Settle a fight that has just ended, if it has."""
    c, fight = player.climber, player.fight
    if fight.outcome is Outcome.ONGOING:
        return
    player.fight = None
    if fight.foe.kind == rules.CLIMBER:
        victim = {"victim": fight.target_id, "name": fight.foe.name}
        player.scene = CAMP
        if fight.outcome is Outcome.WON:
            rules.apply_victory(rng, c, fight)               # the XP; the purse is settled by the route
            player.happenings.append((ROBBED, victim))
        elif fight.outcome is Outcome.FLED:
            player.notice.append(text.ROB_FLED)
        else:
            player.notice.append(text.ROB_LOST.format(name=fight.foe.name))
            drachmae, xp = rules.apply_death(c)
            player.happenings.append((FELL_TO, {**victim, "purse": drachmae, "level": c.level}))
            player.notice += [line.format(drachmae=drachmae, xp=xp) for line in text.DEATH]
            player.scene = DEAD
        return
    if fight.foe.kind == rules.GATEKEEPER:
        _, won, lost = text.GATEKEEPERS[c.level - 1]
        if fight.outcome is Outcome.WON:
            rules.apply_level_up(c)
            player.notice += [won, text.LEVEL_UP.format(band=data.BANDS[c.level - 1], level=c.level)]
            player.happenings.append((LEVEL_GAINED, with_article(fight.foe)))
        else:
            player.notice.append(lost)
        player.scene = PALAESTRA
        return
    if fight.foe.kind == rules.LADON and fight.outcome is Outcome.WON:
        rules.apply_ascent(c)
        # The day is done: you come round in the Foothills at evening.
        c.fights_left = c.duels_left = 0
        player.notice += list(text.ASCENT)
        player.notice.append(text.ASCENT_COUNT.format(n=c.ascents, title=rules.title(c.ascents)))
        player.happenings.append((ASCENDED, fight.foe.name))
        player.scene = SUMMIT
        return
    if fight.outcome is Outcome.WON:
        if fight.foe.kind == rules.CREATURE:
            player.notice.append(text.FOES[fight.foe.name][1])
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
        if fight.foe.kind == rules.LADON:
            player.notice.append(text.LADON_WINS)
        player.happenings.append((DIED, with_article(fight.foe)))
        drachmae, xp = rules.apply_death(c)
        player.notice += [line.format(drachmae=drachmae, xp=xp) for line in text.DEATH]
        player.scene = DEAD


def _start_fight(rng: Random, player: Player, foe: rules.Foe) -> None:
    player.fight = rules.open_fight(rng, player.climber, foe)
    player.scene = FIGHT
    player.notice.append(text.FIGHT_OPENS.format(foe=with_article(foe)))
    if foe.kind == rules.CREATURE:
        player.notice.append(text.FOES[foe.name][0])
    player.notice += _narrate(player.fight)
    _after_blows(rng, player)


def _event_outcome(rng: Random, player: Player, result: rules.EventResult) -> None:
    player.notice.append(text.EVENT_RESULT[result.key].format(n=result.n))
    if result.news:
        player.happenings.append((KID_HOME, ""))
    if result.foe is not None:
        _start_fight(rng, player, result.foe)


def act(rng: Random, player: Player, action: str, amount: int = 0, words: str = "",
        camp: list[Target] | None = None, people: list[Person] | None = None) -> None:
    """Perform one action from the player's current screen, or raise NotOffered."""
    offered = {choice.action: choice for choice in screen(player, camp, people).choices}
    if action not in offered:
        raise NotOffered(action)
    c = player.climber
    player.notice = []
    player.happenings = []

    if action.startswith("go:"):
        player.scene = action.removeprefix("go:")
        if player.scene != SUITOR:
            player.event = None

    elif action.startswith("court:"):
        regular = action.removeprefix("court:")
        name = text.REGULAR_NAMES[regular]
        result = rules.apply_courtship(rng, c, regular)
        if not result.won:
            player.notice.append(text.COURT_LOST[result.step - 1].format(name=name))
        else:
            player.notice += [text.COURT_WON[regular][result.step - 1], text.COURT_XP.format(xp=result.xp)]
            if result.charmed:
                player.notice.append(text.COURT_CHARMED)
            if result.married:
                player.notice.append(text.WEDDING_REGULAR.format(name=name))
                player.happenings.append((WED_REGULAR, name))

    elif action == "part":
        name = text.REGULAR_NAMES[rules.courting(c)]
        rules.apply_parting(c)
        player.notice.append(text.PARTED.format(name=name))

    elif action in ("heart:open", "heart:close"):
        c.open_heart = action == "heart:open"
        player.notice.append(text.HEART_OPENED if c.open_heart else text.HEART_SHUT)

    elif action.startswith("suitor:"):
        player.event, player.scene = action.removeprefix("suitor:"), SUITOR

    elif action in ("flirt", "propose", "accept", "decline", "divorce", "door:shut", "door:open"):
        person = _suitor(player, people)
        who = {"id": person.user_id, "name": person.name}
        if action == "flirt":
            c.flirted_today = True
            player.notice.append(text.FLIRTED.format(name=person.name))
            player.happenings.append((FLIRT, who))
        elif action == "propose":
            player.notice.append(text.PROPOSED.format(name=person.name))
            player.happenings.append((PROPOSE, who))
        elif action == "accept":
            rules.apply_wedding(c, person.user_id)
            player.notice.append(text.ACCEPTED.format(name=person.name))
            player.happenings.append((ACCEPT, who))
        elif action == "decline":
            player.notice.append(text.DECLINED.format(name=person.name))
            player.happenings.append((DECLINE, who))
        elif action == "divorce":
            rules.apply_parting(c)
            player.notice.append(text.DIVORCED.format(name=person.name))
            player.happenings.append((DIVORCE, who))
            player.scene, player.event = HEARTS, None
        else:
            shut = action == "door:shut"
            player.notice.append((text.DOOR_SHUT if shut else text.DOOR_OPENED).format(name=person.name))
            player.happenings.append((SHUT_DOOR if shut else OPEN_DOOR, who))

    elif action == "seek":
        c.fights_left -= 1
        if rules.is_event(rng):
            kind = rules.roll_event(rng, c)
            if kind in data.INSTANT_EVENTS:
                _event_outcome(rng, player, rules.resolve_event(rng, c, kind))
            else:
                player.event, player.scene = kind, EVENT
        else:
            _start_fight(rng, player, rules.random_creature(rng, c))

    elif action.startswith("event:"):
        try:
            result = rules.resolve_event(rng, c, player.event, action.removeprefix("event:"), amount)
        except ValueError:
            player.notice.append(text.KNUCKLES_REFUSED)      # a stake he will not take; ask again
            return
        player.event, player.scene = None, SLOPES
        _event_outcome(rng, player, result)

    elif action == "knucklebones":
        try:
            won = rules.apply_knucklebones(rng, c, amount)
            player.notice.append((text.KNUCKLES_WON if won else text.KNUCKLES_LOST).format(n=amount))
        except ValueError:
            player.notice.append(text.KNUCKLES_REFUSED)

    elif action.startswith("calling:"):
        rules.apply_new_calling(c, action.removeprefix("calling:"))
        player.notice.append(text.NEW_CALLING.format(calling=data.CALLINGS[c.calling][0], rank=c.rank))

    elif action.startswith("fight:"):
        rules.take_turn(rng, c, player.fight, action.removeprefix("fight:"))
        player.notice += _narrate(player.fight)
        _after_blows(rng, player)

    elif action.startswith("rob:"):
        target = next(t for t in camp if f"rob:{t.user_id}" == action)
        c.duels_left -= 1
        if target.in_room:
            c.key = False
        player.happenings.append((ATTEMPTED, target.user_id))
        player.fight = rules.open_fight(rng, c, target.foe)
        player.fight.target_id = target.user_id
        player.scene = FIGHT
        opens = text.ROB_OPENS_ROOM if target.in_room else text.ROB_OPENS
        player.notice.append(opens.format(name=target.name))
        player.notice += _narrate(player.fight)
        _after_blows(rng, player)

    elif action == "key":
        try:
            player.notice.append(text.KEY_BOUGHT.format(price=rules.apply_key(c)))
        except ValueError:
            player.notice.append(text.KEY_REFUSED)

    elif action == "song":
        song, n = rules.apply_song(rng, c)
        name, lyric, blessing = text.SONGS[song]
        player.notice += [name, *lyric, blessing.format(n=n)]

    elif action == "room":
        try:
            player.notice.append(text.ROOM_TAKEN.format(price=rules.apply_room(c)))
        except ValueError:
            player.notice.append(text.ROOM_REFUSED)

    elif action == "wine":
        try:
            price, healed = rules.apply_wine(c)
            player.notice.append(text.WINE.format(price=price, healed=healed))
            player.notice.append(text.GOSSIP[rng.randint(0, len(text.GOSSIP) - 1)])
        except ValueError:
            player.notice.append(text.WINE_REFUSED)

    elif action == "wall:write":
        try:
            line = rules.clean_wall_line(words)
            if contains_url(line):
                raise ValueError("no links")
        except ValueError:
            player.notice.append(text.WALL_REFUSED)
        else:
            c.wall_today += 1
            player.happenings.append((WROTE, line))
            last = c.wall_today >= data.WALL_LINES_PER_DAY
            player.notice.append(text.WALL_WRITTEN_LAST if last else text.WALL_WRITTEN)

    elif action == "garden":
        c.fights_left -= 1
        c.gate_tried_today = True
        player.fight = rules.open_fight(rng, c, rules.ladon(c.ascents))
        player.scene = FIGHT
        player.notice += [text.SEEK_GARDEN, *text.LADON_OPENS]
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
