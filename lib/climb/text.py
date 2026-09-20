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
FIGHT_OPENS = "Something moves on the path ahead: {foe}."
AMBUSH = "It saw you first."

# One line for every event the rules can report; a test checks none is missing.
# {foe} is the enemy mid-sentence ("the Irritable Goat", "Kleitos Two-Dogs"),
# {Foe} the same at the start of one; {hits} and {is} agree with it in number.
EVENTS = {
    "ambush": AMBUSH,
    "you_hit": "You strike {foe} for {n}.",
    "mighty": "A mighty blow!",
    "fury": "Ares takes your arm for a moment. You strike {foe} for {n}.",
    "flame": "Hecate's fire leaps from your hand at {foe}: {n}. Whatever comes back next will have less behind it.",
    "quick_hands": "You strike {foe} for {n}, and come away with something that jingles.",
    "mend": "You whisper what the torch taught you. {n} hit points return.",
    "foe_hits": "{Foe} {hits} you for {n}.",
    "foe_falls": "{Foe} {is} beaten.",
    "you_fall": "The sky tips over, and goes dark.",
    "fled": "You run. It is not dignified, but you are alive.",
    "shadow": "You step sideways into a shadow that was not there a moment ago.",
    "run_failed": "You turn to run and the scree slides out from under you.",
    "stone_saves": (
        "The blow should have finished you. Instead the ground itself seems to take "
        "it, the way a stone takes rain, and you are somehow back on the path, alone."
    ),
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

# ---------------------------------------------------------------------------
# The Garden
# ---------------------------------------------------------------------------

SEEK_GARDEN = "Past the wall, through the gate Aigle showed you, the garden is very quiet."
GARDEN_TRIED = "You have been to the garden once today. Nobody goes twice."
LADON_OPENS = (
    "The tree is smaller than you expected, and the apples brighter. What you took "
    "for its roots uncoils. A hundred heads turn, unhurried, to look at you.",
)
LADON_HEADS = "Ladon: {heads} of a hundred heads still watching you."
LADON_ONE_HEAD = "Ladon: one head left, and it has stopped being unhurried."
LADON_WINS = "The last thing you see is how many of him there are."

ASCENT = (
    "The last head sinks into the grass. It is suddenly possible to hear bees.",
    "You reach up and take an apple. It is warm, and heavier than gold should be.",
    "You sit down under the tree to look at it, just for a moment.",
    "When you wake it is evening and you are in the Foothills, in a wool cloak, "
    "with an olive branch across your knees. The apple is gone; the mountain is "
    "exactly where it was. Somewhere above, a great many heads are growing back.",
    "You find that you are smiling.",
)
ASCENT_COUNT = "That is ascent number {n}. In Ephyra they will call you {title}."
SUMMIT_REST = "Tomorrow, the climb. Today you have done enough."

# ---------------------------------------------------------------------------
# The Stele
# ---------------------------------------------------------------------------

STELE = (
    "The Stele stands at the north end of the Agora, where the path begins. Names "
    "are cut into it, and recut, as climbers pass one another on the way up.",
)
STELE_EMPTY = "The stone is blank. Somebody has to be first."

# ---------------------------------------------------------------------------
# The Lethe House
# ---------------------------------------------------------------------------

LETHE = (
    "The Lethe House. Low beams, a good fire, and a sign over the bar that says "
    "NO ONE REMEMBERS THEIR TAB, which Nikandros insists is a joke.",
    "Orpheus sits by the hearth, tuning. Kalliste and Theron have the corner "
    "table, as they do most nights.",
)
LETHE_ROOMED = "You have a room upstairs tonight. Nobody will trouble you there."
ORPHEUS_DONE = "Orpheus has sung for you today. He nods, and goes back to tuning."

# Each song: four lines of lyric, then what it does. {n} is the size of the blessing.
SONGS = {
    "road": ("The Road Goes Up", (
        "The road goes up, and so do you,",
        "there being nothing else to do;",
        "and if your legs complain of stone,",
        "remind them they are not alone."),
        "Your legs feel new. You can climb {n} more times today."),
    "bronze": ("Bronze and Breath", (
        "Bronze for the arm and breath for the chest,",
        "the smith makes one, the hill the rest;",
        "breathe in the height, breathe out the fear,",
        "and carry more of yourself from here."),
        "You are healed, and until dawn you have {n} more hit points than you did."),
    "ferryman": ("What the Ferryman Owes", (
        "He took a coin from everyone",
        "who ever crossed, and gave back none;",
        "so when you find one in the grass,",
        "say thank you to him as you pass."),
        "Under your stool is a purse nobody claims: {n} drachmae."),
    "goatherd": ("The Goatherd's Daughter", (
        "She knew the hill before the hill",
        "knew her; she walks it, laughing, still.",
        "Ask her the way. She will not say,",
        "but watch her feet, and learn the way."),
        "You understand something about footing that you did not before: {n} XP."),
    "sisters": ("Nine Sisters", (
        "Nine sisters sat upon a wall",
        "and taught the first of us to call",
        "the thing we need by its right name.",
        "It comes. It has not always came."),
        "Orpheus winces at his own rhyme. Still: you may call on your calling {n} more time today."),
    "stone": ("A Stone Remembers", (
        "A stone remembers every hand",
        "that pushed it, and will understand;",
        "so when the dark comes for your breath,",
        "the stone will take it, and not death."),
        "You are not sure what that meant. You feel oddly safe. Your next fight to the death will not be one."),
    "eurydice": ("Eurydice, Almost", (
        "I did not look. I swear I did not look",
        "until the very last step that I took.",
        "If you love someone, friend, walk on ahead,",
        "and trust the footsteps. That is all I've said."),
        "The room is quiet for a while. People look at you more kindly afterwards: Charm +{n}."),
    "string": ("(He breaks a string.)", (
        "Orpheus plays four notes, and the fifth goes TWANG.",),
        "\"It happens,\" he says, sucking his finger. \"Come back tomorrow.\""),
}

ROOM_OFFER = "A room for the night is {price} drachmae. Upstairs, nobody can rob you."
ROOM_TAKEN = "Nikandros takes {price} drachmae and hands you a key with a wooden fish on it."
ROOM_REFUSED = "Nikandros looks at your purse, then at you, with sympathy but no key."
WINE = "Nikandros pours. {price} drachmae; {healed} hit points of warmth go down with it."
WINE_REFUSED = "\"On the house\" is not a phrase Nikandros knows."
GOSSIP = (
    "\"Bank before you climb,\" says Nikandros. \"The mountain keeps what it finds on you.\"",
    "\"Doros talks rot,\" says Nikandros, \"but his armour is sound. Most lose at the gate for want of it.\"",
    "\"Akeso is cheaper than dying,\" says Nikandros. \"Most people work that out second.\"",
    "\"They say the garden needs the best bronze there is. They say it from the Palaestra sand, mostly.\"",
    "\"Makaria's seeds,\" says Nikandros, lowering his voice. \"What they buy, you keep. Even after.\"",
    "\"That fellow with the boulder? Help him if you see him. He's better company than he looks.\"",
    "\"Orpheus sings once a day for anyone. Costs nothing. People forget to ask.\"",
)

WALL = "The wall by the door is soft plaster, and generations of climbers have scratched their thoughts into it."
WALL_EMPTY = "Nobody has written anything lately. The plaster is smooth and inviting."
WALL_WRITTEN_LAST = "That is five today. Nikandros is looking at you over the rim of a cup he is pretending to polish."
WALL_WRITTEN = "You scratch it in with the point of your knife. It looks permanent. It is not."
WALL_FULL = "Nikandros coughs. \"Five a day,\" he says. \"It's a wall, not a diary.\""
WALL_REFUSED = "The plaster will not take that. (One line, up to 120 characters, and no links.)"

# ---------------------------------------------------------------------------
# The Herald
# ---------------------------------------------------------------------------

HERALD = (
    "Stentor stands on his barrel, as he does every morning, telling the town what "
    "it already knows at a volume it cannot ignore.",
)
HERALD_QUIET = "\"NOTHING HAS HAPPENED,\" bellows Stentor, \"AND I WILL KEEP YOU INFORMED.\""

# {name} is a climber; {detail} depends on the kind of news. Variants rotate.
NEWS = {
    "wed_regular": (
        "{name} and {detail} were married at the festival fire. Nikandros wept, and blamed the smoke.",
    ),
    "accept": (
        "{name} and {detail} were married at the festival fire. They met on the mountain. Most people only meet goats.",
    ),
    "divorce": (
        "{name} and {detail} are no longer married. Stentor has been asked to say no more, and will not. NO MORE.",
    ),
    "robbed": (
        "{name} robbed {detail} in the night. {detail} is advised to bank their coin.",
        "{detail} woke poorer. {name} was seen leaving the Camp, whistling.",
    ),
    "fell_to": (
        "{name} tried to rob {detail} and was beaten by someone who was technically asleep.",
    ),
    "kid": (
        "{name} came down the mountain with somebody's lost goat on their shoulders. The goat is said to be unrepentant.",
    ),
    "arrival": (
        "{name} has come to Ephyra with an olive branch and an expression of confidence.",
        "A newcomer: {name}. Agathe has been told.",
    ),
    # {detail} is whoever was beaten or did the beating, with its article;
    # {Detail} the same at the start of a sentence. Past tense throughout, so
    # that "Damon and Lykos" and "the Twin Vipers" need no special verbs.
    "level": (
        "{name} got past {detail} and now stands in {band}.",
        "{Detail} stepped aside for {name}. {band} will see what they are made of.",
    ),
    "death": (
        "{name} was carried down from {band}, the work of {detail}. They will be fine by morning.",
        "{Detail} sent {name} back to Akeso. She has the good thyme out.",
    ),
    "ascent": (
        "{name} HAS COME DOWN WITH AN APPLE. That is ascent number {detail}. Ladon is said to be furious.",
    ),
}

# One a day, by the calendar.
DAILY = (
    "A goat was found on the roof of the Vault. Kallias is counting it.",
    "Brontes was heard to say a whole sentence. Witnesses disagree about what it was.",
    "Rain on the Goat Tracks. Myrto advises sensible footwear, as she has for thirty years.",
    "Doros is giving a talk on swordsmanship tonight. Attendance is expected to be Doros.",
    "Orpheus has new strings. He would like everyone to stop mentioning the old ones.",
    "Snow reported above the Eagle Crags, which is where snow is kept.",
    "Akeso reminds climbers that \"walking it off\" is not a treatment.",
    "Someone has carved \"LADON IS A LIZARD\" on the Stele. Someone is advised to be careful.",
    "The goat that belongs to nobody has been seen following a tax collector. Hopes are high.",
    "Makaria sold no seeds today, or yesterday, or ever. She gives them and takes them. It is different.",
    "Clear skies. From the Agora you can see almost to the Cloud Line, which is as far as most want to.",
    "Nikandros has watered the wine. Nikandros denies watering the wine. The wine has no comment.",
)

# ---------------------------------------------------------------------------
# The Slopes: events
# ---------------------------------------------------------------------------

# What you see when an event asks you to choose.
EVENT_INTRO = {
    "boulder": (
        "The path is blocked by a boulder the size of a small house. Leaning against "
        "it, getting his breath, is a man with enormous shoulders and an unexpectedly "
        "cheerful face.",
        "\"Nearly there,\" he says. He says it the way other people say good morning. "
        "\"I could use a hand, if you have one.\"",
    ),
    "wall": (
        "An old orchard wall runs along the path. Over it, just within reach, hangs a "
        "single pomegranate, split and glittering.",
        "It is not your pomegranate.",
    ),
    "satyr": (
        "A satyr is sitting on a wineskin the size of a goat. \"Drinking contest,\" he "
        "says, without preamble. \"Name your stake. I never lose.\" He hiccups.",
    ),
    "kid": (
        "A goat kid is standing on a rock, bleating at the sky. It is wearing a bell. "
        "Somebody, down in Ephyra, is missing it.",
    ),
    "shrine": (
        "Where two paths cross there is a heap of stones with a weathered head on top: "
        "a shrine to Hermes, who looks after travellers, and also thieves.",
    ),
    "hive": (
        "A cleft in the rock is humming. Bees come and go. It smells of thyme honey, "
        "and of a bad idea.",
    ),
    "toll": (
        "A large person is sitting on a smaller rock in the middle of the path. "
        "\"Toll,\" says the large person, holding out a hand like a shovel.",
    ),
}

# Button labels for each option, with the hotkey in brackets.
EVENT_OPTIONS = {
    "boulder": {"help": ("h", "(H)elp him push"), "around": ("g", "(G)o around")},
    "wall": {"take": ("t", "(T)ake it"), "leave": ("l", "(L)eave it")},
    "satyr": {"wager": ("w", "(W)ager"), "decline": ("d", "(D)ecline")},
    "kid": {"carry": ("c", "(C)arry it down to town"), "sell": ("s", "(S)ell it to a passing drover"), "leave": ("l", "(L)eave it")},
    "shrine": {"offer": ("o", "Leave an (O)ffering"), "pass": ("p", "(P)ass by")},
    "hive": {"reach": ("r", "(R)each in"), "leave": ("l", "(L)eave the bees alone")},
    "toll": {"pay": ("p", "(P)ay the toll"), "fight": ("f", "(F)ight"), "back": ("b", "Turn (B)ack")},
}

# What came of it. {n} is whatever number the result carries.
EVENT_RESULT = {
    "spring": "A spring comes out of the rock here, so cold it aches. You drink until you are whole again: {n} hit points.",
    "rockslide": "The slope above you lets go. You are fast, but not fast enough to keep all of yourself: {n} hit points lost.",
    "eagle": "An eagle passes overhead and lets something fall. It is a purse, only slightly pecked: {n} drachmae.",
    "oracle": "An old woman on the path looks through you. \"{n} XP,\" she says, \"and then the gate.\" She does not explain, and you find you do not need her to.",
    "oracle_ready": "An old woman on the path looks through you. \"Nothing more to learn down here,\" she says. \"Only the gate. Go and knock.\"",
    "oracle_garden": "An old woman on the path looks through you. \"You have run out of mountain,\" she says. \"What is left is the garden, and your best bronze, and your nerve.\"",
    "shade": "A figure sits where the path turns, grey as morning, practising something over and over. It is a climber who did not come back. Wordlessly they show you what they had almost learned. Your calling rank is now {n}.",
    "smoke": "Smoke between the pines. You follow it to a fire with shepherds round it, who shift up to make room as if they had been expecting you. You will know the way to the Shepherds' Fire from now on.",
    "boulder_help": "You put your shoulder to it. It is like pushing the world. It moves, a little; he laughs, delighted. It costs you {n} hit points and teaches you something about persistence. \"Same time tomorrow,\" he says.",
    "boulder_lesson": "You push together for a long time ({n} hit points' worth). At the top of the rise he shows you how he sets his feet, a thing he has had for ever to get right. Your calling deepens by a rank. Behind you, the boulder begins, gently, to roll back down.",
    "boulder_around": "You edge past. \"Another time,\" he says, without reproach, and sets his shoulder to the stone.",
    "wall_take": "It comes away in your hand. One seed is perfect. You now have {n}.",
    "wall_gardener": "It comes away in your hand, and so, from behind the wall, does a gardener with a pruning hook and a very firm view of property.",
    "wall_leave": "You leave it. The orchard seems, in some way, to notice.",
    "satyr_won": "You match him cup for cup until he slides gently off the wineskin. You are {n} drachmae richer and will regret nothing until morning.",
    "satyr_lost": "He never loses. You wake under a bush, {n} drachmae poorer, with a view of the path from an unfamiliar angle.",
    "satyr_decline": "\"Your loss,\" says the satyr, who then falls asleep mid-sentence.",
    "kid_carry": "You carry it down on your shoulders, bell clanking. A small girl in the Agora bursts into tears of joy. People saw. Your Charm is now {n}.",
    "kid_sell": "A drover gives you {n} drachmae for it and asks no questions. The bell goes on clanking for some time.",
    "kid_leave": "You leave it bleating. It will probably be fine. Goats usually are.",
    "shrine_pleased": "You lay your coins on the stones. A breeze gets up from nowhere and your pack feels lighter. You can climb {n} more times today.",
    "shrine_silent": "You lay your coins on the stones. Nothing happens, which with Hermes is sometimes the best you can hope for.",
    "shrine_pass": "You nod to the stone head and walk on. It does not nod back.",
    "hive_honey": "You come away with a fistful of comb and, miraculously, no stings. It is the best thing you have ever eaten. Your maximum hit points rise by {n}, for good.",
    "hive_stung": "The bees have views. {n} hit points later, you have none of the honey and a new respect for bees.",
    "hive_leave": "You leave the bees to it. The humming sounds, if anything, smug.",
    "toll_pay": "You count {n} drachmae into the enormous hand. The large person shifts, slightly, to one side.",
    "toll_fight": "\"No,\" you say. The large person stands up, and keeps standing up for some time.",
    "toll_back": "You turn round. There are other paths. Most of them are worse.",
}

SATYR_STAKE = "He will take any stake up to {most} drachmae."

# ---------------------------------------------------------------------------
# The Shepherds' Fire
# ---------------------------------------------------------------------------

FIRE = (
    "The Shepherds' Fire. Nobody here asks your name, and everybody seems to know "
    "it. There is a pot of something on the embers, and a game going on a flat rock.",
    "An old shepherd watches you over the flames. \"Callings change,\" she says. "
    "\"Half of what you know comes with you. The rest you leave at the fire.\"",
)
FIRE_GAMES = "Knucklebones: even money, up to {most} drachmae a throw, {left} more today."
FIRE_NO_GAMES = "The knucklebones are put away; you have played enough for one day, or have nothing to play with."
KNUCKLES_WON = "The bones fall your way. {n} drachmae slide across the rock to you."
KNUCKLES_LOST = "The bones fall badly. {n} drachmae slide across the rock, away from you."
KNUCKLES_REFUSED = "The shepherds look at your stake, then at each other. No."
NEW_CALLING = "You sit a long while by the fire. When you stand, you follow {calling}, at rank {rank}, and something you used to know has gone quiet."

# ---------------------------------------------------------------------------
# The Camp
# ---------------------------------------------------------------------------

CAMP = (
    "The Camp, on the flat ground below the first olives, where climbers without "
    "the price of a room roll up in their cloaks. It is dark, and everyone here is "
    "asleep, or pretending to be.",
    "Nobody will thank you for what you are thinking of doing.",
)
CAMP_SPENT = "You have done enough skulking for one night."
CAMP_EMPTY = "Nobody here is worth the risk, or within your reach."
CAMP_KEY = "Nikandros' key is in your pocket. One of the doors upstairs will open to it."
SLEEPER = "{name}, {title}, asleep beside the {weapon}, in the {armour}."
SLEEPER_ROOM = "{name}, {title}, asleep upstairs at the Lethe House, with the {weapon} within reach."
ROB_OPENS = "You pick your way between the sleepers to {name}, and reach for the purse. {name} wakes."
ROB_OPENS_ROOM = "The key turns. {name} is awake before the door is fully open."
ROBBED_THEM = "{name} goes down. The purse is yours: {drachmae} drachmae."
ROBBED_NOTHING = "{name} goes down. The purse is empty. They banked it, as sensible people do."
ROB_FLED = "You melt back into the dark before anyone else wakes."
ROB_LOST = "{name} was better than they looked asleep."

KEY_OFFER = "\"There is a key,\" says Nikandros, very quietly, \"for {price} drachmae. One door, tonight only. I never said so.\""
KEY_BOUGHT = "Nikandros palms {price} drachmae and slides something across the bar under a cloth."
KEY_REFUSED = "Nikandros has no idea what you are talking about."

# Left for the victim to find.
MAIL_ROBBED = "While you slept, {name} robbed you: {drachmae} drachmae gone, and {xp} XP of peace of mind. Bank your coin; rent a room."
MAIL_ROBBED_EMPTY = "While you slept, {name} went through your things and found an empty purse. You lost {xp} XP of peace of mind, and nothing else."
MAIL_DEFENDED = "While you slept, {name} tried to rob you, and you beat them without properly waking. Their purse ({drachmae} drachmae) is yours, and {xp} XP."

# ---------------------------------------------------------------------------
# Asking about the others, at the Fire
# ---------------------------------------------------------------------------

OTHERS = (
    "\"Who's on the mountain?\" The old shepherd pokes the fire. \"We see everyone go "
    "up. We see what they carry. We see where they sleep.\"",
)
OTHERS_EMPTY = "\"Just you,\" she says. \"For now.\""

# ---------------------------------------------------------------------------
# The corner table: Kalliste and Theron
# ---------------------------------------------------------------------------

CORNER = (
    "The corner table. Kalliste, who makes the best wine on this side of the "
    "mountain and knows it, is arguing with Theron, who hunts the high pines and "
    "is shy everywhere except there.",
)
REGULAR_NAMES = {"kalliste": "Kalliste", "theron": "Theron"}
COURT_STEPS = (
    "catch their eye", "stand them a cup of wine", "trade stories", "walk by the river",
    "bring a gift", "dance at the festival fire", "meet the family", "ask",
)
COURT_STATUS = "With {name} you have got as far as: {done}. Next: {next} (Charm {need})."
COURT_FRESH = "You have not tried your luck with either of them. It starts with catching an eye (Charm 1)."
COURT_WED = "You are married to {name}, who saves you the good chair."
COURT_NEED_CHARM = "To {next} you would need Charm {need}. You have {charm}. Be kinder to goats."
COURT_NEED_GIFT = "A proper gift will cost {price} drachmae, and you do not have it in hand."
COURT_TOMORROW = "You have made your move for today. Hovering is not attractive."
COURT_TAKEN = "Your heart is spoken for elsewhere, and both of them know it."
COURT_OTHER = "{name} has noticed you courting {other}. One at a time."

# What happens on each step, per regular, when it goes well.
COURT_WON = {
    "kalliste": (
        "Kalliste looks up from her cup, finds you looking, and does not look away first. She never does.",
        "\"You're buying? Then I'm choosing,\" says Kalliste, and orders her own vintage. She lets you taste it. It is very good and she watches you realise that.",
        "You tell her about the Tax Collector. She tells you about the year the frost took the whole south slope, and what she did about it. You talk until Nikandros puts the stools up.",
        "You walk by the river. She names every vineyard you can see, and who owns it, and what they are doing wrong. At the bridge she takes your arm as if it had been her idea.",
        "She turns the gift over, twice. \"Nobody buys me things,\" she says. \"They assume I have them.\" She wears it the next day, where everyone can see.",
        "At the festival fire Kalliste dances the way she argues: to win. You keep up, just. When the music stops she is laughing too hard to say anything cutting.",
        "Her mother inspects you like a doubtful cask. Her three brothers inspect you like a delivery. By the end of the evening you have been told you may call again, which Kalliste says is unprecedented.",
        "\"Yes,\" says Kalliste, before you have finished. \"Obviously. I decided at the river. I have been waiting for you to catch up.\"",
    ),
    "theron": (
        "Theron glances up, sees you, goes red to the ears, and knocks over the salt. But he smiles.",
        "He says thank you for the wine three times. Then, to the cup, very quietly: \"People don't usually sit with me. It's nice.\"",
        "Once he starts on the high pines he forgets to be shy: the wolves he knows by sight, the place where you can see both seas. You could listen all night, and do.",
        "You walk by the river. He shows you an otter's slide you would never have seen. He holds your hand as if it might startle.",
        "He opens the gift very carefully and is silent so long you think you have got it wrong. \"I'll keep it in the hills with me,\" he says at last, and you understand that is the highest place he has.",
        "Theron cannot dance and knows it and dances anyway, because you asked. It is the bravest thing anyone does in Ephyra that year.",
        "His family live a day's walk up, in a house that smells of pine smoke. His grandmother, who is tiny and terrifying, looks you up and down and says, \"Finally.\"",
        "He has clearly rehearsed an answer in case you ever asked. He forgets all of it. \"Yes,\" he manages. \"Yes. Sorry. Yes.\"",
    ),
}
# When it does not. One per step; {name} is whoever you tried it with.
COURT_LOST = (
    "{name} looks up, but it turns out to be at someone behind you.",
    "{name} accepts the wine, thanks you, and goes on talking to the table.",
    "You get halfway through your best story and realise {name} has heard it. From the person it actually happened to.",
    "It rains. {name} remembers somewhere to be.",
    "{name} thanks you for the gift in the tone people use for socks.",
    "You tread on {name}'s foot in front of the whole festival. Twice. The same foot.",
    "The family are polite. It is the politeness that worries you.",
    "\"Ask me again,\" says {name}, not unkindly, \"when you mean it as much as I would have to.\"",
)
COURT_XP = "Whatever else, you learn something: {xp} XP."
COURT_CHARMED = "You come away a little easier in your own skin: Charm +1."
WEDDING_REGULAR = "You and {name} are married at the festival fire, with half the town watching and Orpheus, for once, playing something cheerful."
PARTED = "You tell {name} it is over. It is a small town; you will see them every day. Charm -2."
SPOUSE_GIFT = "{name} left {n} drachmae by the bed and a note that says to be careful."
SPOUSE_FIGHTS = "{name} was on the mountain yesterday and came home full of advice. You can climb {n} more times today."

# ---------------------------------------------------------------------------
# Other climbers
# ---------------------------------------------------------------------------

HEARTS = (
    "There are other climbers in Ephyra, and some of them are good company.",
)
HEART_CLOSED = (
    "Your heart is closed to other climbers: nobody can flirt with you, and you "
    "cannot with them. That is how everyone starts. It is entirely up to you."
)
HEART_OPEN = "Your heart is open to other climbers who have opened theirs."
HEART_OPENED = "You let it be known, in the small ways these things are known, that you would not mind company."
HEART_SHUT = "You let it be known that you are here to climb. Nobody can flirt with you now, and nothing already between you and anyone is lost."
NOBODY_OPEN = "Nobody else has an open heart just now."
PERSON = "{name}, {title}, in {band}."
PERSON_NOTE = {
    "spouse": " You are married.",
    "proposed_to_you": " They have asked you to marry them.",
    "you_proposed": " You have asked; they have not answered.",
    "flirted": " They have flirted with you.",
}
SUITOR_AFFINITY = "Between you and {name}: {affinity} out of the {needed} it takes before anyone asks anything serious."
FLIRTED = "You catch {name}'s eye across the Lethe House and hold it a moment longer than you need to."
MAIL_FLIRT = "{name} caught your eye across the Lethe House, and held it a moment longer than they needed to."
PROPOSED = "You ask {name} to marry you. Now you wait."
MAIL_PROPOSAL = "{name} has asked you to marry them. You will find them at the corner table, trying to look unconcerned."
ACCEPTED = "You say yes. You and {name} are married at the festival fire."
MAIL_ACCEPTED = "{name} said yes. You are married. Orpheus played."
MARRY_TOO_LATE = "You go to say yes and find that {name} is no longer free to hear it."
DECLINED = "You tell {name} no, as kindly as it can be told."
MAIL_DECLINED = "{name} has said no. They were kind about it, which is worse."
DOOR_SHUT = "You close the door on {name}. They will not be told. Nothing they send will reach you."
DOOR_OPENED = "You open the door to {name} again."
DIVORCED = "You and {name} are no longer married. Charm -2."
MAIL_DIVORCED = "{name} has ended your marriage."
