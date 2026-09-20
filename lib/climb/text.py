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

# ---------------------------------------------------------------------------
# Shops
# ---------------------------------------------------------------------------

FORGE = (
    "Brontes' Forge. The smith has one eye and keeps it on his work. Prices are "
    "chalked on the wall; he has never been known to discuss them.",
)
AEGIS_ROW = (
    "Aegis Row. Doros has never been in a fight, and will explain at length how "
    "you should have won your last one.",
)
CARRYING = "You carry: {item}."
ON_OFFER = "{item}: {price} drachmae, with yours in trade."
TOO_DEAR = "{item}: {price} drachmae. (You have {purse}.)"
NOTHING_BETTER = "There is nothing here better than what you have that you are ready to carry."
BEST_THERE_IS = "There is nothing better than what you carry. Brontes almost smiles."
BOUGHT_WEAPON = "Brontes takes {cost} drachmae and your old weapon, and hands you the {item} without a word."
BOUGHT_ARMOUR = "Doros takes {cost} drachmae, fits the {item}, and tells you where to stand when wearing it."

# ---------------------------------------------------------------------------
# The Orchard Gate
# ---------------------------------------------------------------------------

ORCHARD = (
    "An old wall, a gate that does not quite close, and beyond it pomegranate "
    "trees in rows older than the town. Makaria is pruning. She does not look up.",
    "\"Two seeds,\" she says. \"What they give, the mountain cannot take back.\"",
)
ORCHARD_SEEDS = "You have {seeds}."
ORCHARD_POOR = "She glances at your hands. \"Come back with two.\""
GIFTS = {
    "strength": "She presses the seeds into your palm and closes your fist over them. Strength +{n}, for good.",
    "defence": "She touches your shoulder with a cold seed. Something in you sets like mortar. Defence +{n}, for good.",
    "vigour": "\"Eat them,\" she says. They are sour. Your maximum hit points rise by {n}, for good.",
}

# ---------------------------------------------------------------------------
# The Palaestra and the gatekeepers
# ---------------------------------------------------------------------------

PALAESTRA = (
    "The Palaestra: a sand floor, a colonnade, and Myrto with her wax tablet. "
    "Everyone who has ever gone up the mountain is on that tablet somewhere.",
)
GATE_AHEAD = "At the top of {band} waits {name}."
GATE_NOT_READY = "\"Not yet,\" says Myrto. \"You have {xp} of the {needed} XP that band has to teach.\""
GATE_READY = "\"You are ready, or as ready as anyone is,\" says Myrto. \"No running, and nobody dies. Shall I send word?\""
GATE_TRIED = "\"One attempt a day,\" says Myrto, not unkindly. \"Go and sleep on what you learned.\""
GATE_TOP = (
    "\"There is nobody left for me to send you to,\" says Myrto. \"Past the wall is "
    "the garden, and what is in the garden is not on my tablet.\""
)
GATE_OPENS = "Word is sent. You climb to the top of {band}, and {name} is waiting."
LEVEL_UP = "The way is open. You stand in {band}, level {level}, healed and a little wiser in your calling."

# For each gatekeeper: how they greet you, what they say when you win, and the
# critique you get when you do not.
GATEKEEPERS = (
    ("Agathe leans on her staff among the goats. \"Everyone wants to go up,\" she says. \"Show me you can stay up.\"",
     "Agathe rubs her shin. \"Fine. Mind the olives; Stavros counts them.\"",
     "You wake on the Palaestra sand. Agathe's verdict, relayed by Myrto: \"Feet. You have two. Use both.\""),
    ("Old Stavros sets down his pruning hook, slowly, and picks up a much larger one.",
     "\"Sixty years,\" says Stavros, \"and the young still hit harder every season. Go on up.\"",
     "You wake on the sand. Stavros sent down a note: \"You swing like you are apologising.\""),
    ("Kleitos whistles. Two dogs appear from nowhere, grinning. So does Kleitos.",
     "The dogs lick your hand. Kleitos looks betrayed. \"They like you. Go on, then.\"",
     "You wake on the sand with dog hair on you. Kleitos says: \"Watch the one you are not watching.\""),
    ("Ione steps out from behind a pine you had already looked behind.",
     "Ione unstrings her bow. \"You will do. The scree is worse than I am.\"",
     "You wake on the sand. Ione's message is one word: \"Louder than a boar.\" That is four words. She was annoyed."),
    ("Damon and Lykos are arguing about whose turn it is. They stop when they see you. \"Ours,\" they agree.",
     "\"He let you past,\" says Damon. \"You let him past,\" says Lykos. You leave them to it.",
     "You wake on the sand. The brothers' advice arrives in two halves, by two messengers, and contradicts itself."),
    ("Brother Aither sits cross-legged in the cloud, eyes shut. \"I can hear you thinking,\" he says. \"It is very loud.\"",
     "Aither opens one eye for the first time in years. \"Hm,\" he says, and closes it. The cloud parts.",
     "You wake on the sand. Aither's counsel: \"You fought the man you expected. I was the other one.\""),
    ("Aella raises an arm and the sky fills with wings.",
     "The eagles settle. Aella nods at the snow above. \"They will watch you up. Do not embarrass them.\"",
     "You wake on the sand, lightly pecked. Aella says: \"You looked up. Everyone looks up.\""),
    ("Chione is already standing in your footprints. The air hurts to breathe.",
     "Chione laughs, and it sounds like ice going out on a river. \"Warm-blooded, after all. Pass.\"",
     "You wake on the sand, which is pleasantly warm. Chione sent nothing. The frostbite is the message."),
    ("Zetes is somewhere overhead. You can tell by the shadow, and then by the boot.",
     "Zetes lands, for once, and clasps your arm. \"Hold on to something in the gap. I never do.\"",
     "You wake on the sand. Zetes' advice arrives on the wind: \"Stop fighting where I was.\""),
    ("The Warden stands on the Black Stair and says nothing, as he has for longer than anyone remembers.",
     "The Warden steps aside. It is the most anyone has got out of him in living memory.",
     "You wake on the sand. The Warden said nothing. Myrto says that from him, that is encouragement."),
    ("Aigle sits on the garden wall, eating an apple that is not golden. \"He is awake today,\" she says. \"But first, me.\"",
     "Aigle hops down and unlatches a gate you had not seen. \"I will not wish you luck. Luck is not what he respects.\"",
     "You wake on the sand. Aigle's note: \"You are nearly what the garden needs. Nearly gets eaten.\""),
)
