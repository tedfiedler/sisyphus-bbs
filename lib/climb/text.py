"""Every word The Long Climb says, in one place.

All of it is original to this project (DESIGN.md section 0). Keep it wry, warm,
and PG-13. Strings are plain text: they are escaped on the way to the page, so
nothing here may rely on markup.
"""

TITLE = "The Long Climb"

WELCOME = (
    "Ephyra sits at the foot of a mountain nobody has bothered to name, because "
    "there is only the one. At the top, they say, is a garden; in the garden, a "
    "tree of golden apples; around the tree, a dragon with more heads than is "
    "reasonable.",
    "People go up. Some of them come back down. A few of those come back down "
    "holding an apple, looking thoughtful, and the next morning they start again.",
    "You have an olive branch, a wool cloak, and sixty drachmae. Before you set "
    "out, the mountain would like to know what sort of climber you are.",
)

CALLINGS = {
    "spear": "The Spear, under Ares. When it matters, you hit once and very hard.",
    "torch": "The Torch, under Hecate. Fire now; mending and shadows as you learn.",
    "sandal": "The Sandal, under Hermes. Never surprised, light of finger, quick to leave.",
}

BEGUN = {
    "spear": "Ares does not acknowledge you. His priests say this is a good sign.",
    "torch": "Somewhere a torch gutters, though there is no wind. Hecate has noticed.",
    "sandal": "Your purse feels lighter, then heavier. Hermes is pleased to meet you.",
}

AGORA = (
    "The Agora. Stalls, arguments, a goat that belongs to nobody. The mountain "
    "fills the whole north side of the sky, as it always has.",
)
AGORA_SPENT = "Your legs have done all the climbing they mean to do today."

SLOPES = "The path leaves the last houses behind. You are in {band}."
SLOPES_SPENT = "You have no more climbing in you today. The mountain will keep."
NOTHING_LEFT = "You look for trouble, but your legs refuse to look with you."

FIGHT_OPENS = "Something moves on the path ahead: {foe}."
AMBUSH = "It saw you first."

# One line for every event the rules can report; a test checks none is missing.
EVENTS = {
    "ambush": AMBUSH,
    "you_hit": "You strike {foe} for {n}.",
    "mighty": "A mighty blow!",
    "fury": "Ares takes your arm for a moment. You strike {foe} for {n}.",
    "flame": "Hecate's fire leaps from your hand: {n}. {foe} smoulders, and flinches.",
    "quick_hands": "You strike {foe} for {n}, and come away with something that jingles.",
    "mend": "You whisper what the torch taught you. {n} hit points return.",
    "foe_hits": "{foe} hits you for {n}.",
    "foe_falls": "{foe} is beaten.",
    "you_fall": "The sky tips over, and goes dark.",
    "fled": "You run. It is not dignified, but you are alive.",
    "shadow": "You step sideways into a shadow that was not there a moment ago.",
    "run_failed": "You turn to run and the scree slides out from under you.",
}

SPOILS = "You find {drachmae} drachmae and learn {xp} XP worth of caution."
SEED = "Caught in its fur (or pocket, or teeth) is a single pomegranate seed."
READY_FOR_GATE = "You have learned all this band can teach. Someone at the Palaestra is waiting."

DEATH = (
    "You are dead, which in Ephyra is a temporary embarrassment.",
    "Whatever was in your purse ({drachmae} drachmae) now belongs to the mountain, "
    "and a little of what you had learned ({xp} XP) has gone with it.",
    "Akeso will have you on your feet at dawn. She will not be impressed.",
)
DEAD = (
    "You are dead until dawn. The Vault is untouched; Kallias checked twice.",
    "Come back tomorrow.",
)

DAWN = "Dawn. You are whole, rested, and owe nobody an explanation."
DAWN_AFTER_DEATH = "Dawn. Akeso has put you back together. She says to try ducking."
DAWN_MID_FIGHT = "Whatever you were fighting last night got bored and wandered off."

HYGIEIA = (
    "The House of Hygieia smells of thyme and vinegar. Akeso looks you over the "
    "way a carpenter looks at a wobbly chair.",
)
HYGIEIA_WHOLE = "\"There is nothing wrong with you that I can fix,\" says Akeso."
HYGIEIA_PRICE = "Healing here is {price} drachmae a point. You are missing {missing}."
HEALED = "Akeso works. {points} hit points return, and {cost} drachmae depart."
HEAL_REFUSED = "Akeso names a price. Your purse disagrees."

VAULT = (
    "The Ferryman's Vault. Kallias is counting something, and will start again "
    "if you interrupt.",
    "Coin in the Vault cannot be lost to the mountain, or to anyone who finds you asleep.",
)
DEPOSITED = "Kallias counts {amount} drachmae in. Twice."
WITHDRAWN = "Kallias counts {amount} drachmae out, and sighs."
VAULT_REFUSED = "Kallias raises one eyebrow. The numbers do not work."
