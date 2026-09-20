# The Long Climb — Design

Status: **built.** Design approved 2026-09-20 (review record in §17); all eight
steps of §16 done the same day. What follows is the design as built; where the
build departed from the first draft, the text says so.

A daily-turn adventure game for Sisyphus BBS, in the tradition of the BBS door
games of the early 1990s. You are a climber in the town of Ephyra, at the foot
of a mountain. Each day you get a handful of fights on its slopes. You grow
stronger, buy better bronze, prove yourself to eleven gatekeepers, and at last
reach the garden at the summit, where the hundred-headed dragon **Ladon** guards
a tree of golden apples. Kill him, take an apple — and wake the next morning at
the foot of the mountain, with the whole climb ahead of you again.

One must imagine the climber happy.

---

## 0. Ground rules: this is an original game

These are design constraints, not an afterthought. They hold for every line
written during implementation.

1. **The genre is borrowed; nothing else is.** Daily turn budgets, random
   wilderness encounters, a gear ladder, a bank, an inn where a rented room
   keeps you safe, a bard, courtship, duelling a trainer to advance, robbing
   sleeping players, a town newspaper, and a final boss that resets you are
   conventions shared by a whole family of games. Rules and mechanics are free
   for anyone to use.
2. **Every name, every sentence, every number is ours.** Title, setting,
   characters, shops, items, monsters, events, prose, and balance tables are
   original to this project or drawn from Greek myth, which is in the public
   domain. No text, name, table, or art is reproduced or paraphrased from any
   existing game, from memory or otherwise.
3. **No existing game's name appears in the game.** The credit line, shown on
   the game's title screen, reads: *"In the tradition of the BBS door games of
   the early '90s."*
4. **Numbers are designed, then tested.** §15's tables come from
   `lib/climb/data.py` and are checked by `lib/climb/sim.py`, which plays whole
   climbs with the real rules; none comes from recollection of anyone else's.
   A test fails if any proper noun from another game appears in the code or
   templates.
5. **Where a familiar convention could be done our own way, it is.** Levels are
   *elevation*; the monsters you meet depend on how high you have climbed;
   trainers are *gatekeepers* on the path; the reset is the point of the story
   rather than a consolation prize.

Tone: wry, warm, PG-13. Innuendo at most. No slurs, no cruelty played for
laughs, nothing a sysop would be embarrassed to have on their board.

## 1. Pillars

| Pillar | Meaning |
|---|---|
| **Ten minutes a day** | A full day's play fits in a coffee break. The turn budget is the pacing, and it is what makes people come back tomorrow. |
| **A month to the summit** | A steady first ascent takes about a month (§15). Long enough to matter, short enough to finish. |
| **The town is other people** | News, rankings, a tavern wall, courtship, and the risk of being robbed in your sleep make a single-player loop feel inhabited. |
| **The climb is the reward** | Ascents accumulate. What you learned stays with you; what you owned does not. |

## 2. The world

**Ephyra** — the town at the mountain's foot. (Sisyphus was its king.)

| Place | What it is | Who runs it |
|---|---|---|
| **The Agora** | Town square; the main menu. | — |
| **The Slopes** | The wilderness above town; where fights happen. | — |
| **Brontes' Forge** | Weapons. | **Brontes**, a one-eyed smith of few words and strong opinions. |
| **Aegis Row** | Armour. | **Doros**, who has never once been in a fight and will tell you how to win yours. |
| **House of Hygieia** | Healing, by the hit point. | **Akeso**, brisk, kind, unshockable. |
| **The Ferryman's Vault** | The bank. Coin in the Vault is safe from robbers and from death. | **Kallias**, who counts everything twice. |
| **The Orchard Gate** | Trade pomegranate seeds for permanent gifts. | **Makaria**, who keeps the old orchard and does not explain herself. |
| **The Lethe House** | The tavern: a bard, a wall to scratch messages on, company, and rooms. | **Nikandros** behind the bar; **Orpheus** by the fire. |
| **The Palaestra** | Where you ask to face the next gatekeeper. | **Myrto**, who keeps the list. |
| **The Herald's Board** | Yesterday's and today's news. | **Stentor**, very loud. |
| **The Stele** | The carved ranking of climbers. | — |
| **The Camp** | Where climbers without a room sleep — and can be robbed. | — |
| **The Shepherds' Fire** | A hidden gathering on the Slopes. Found, not listed. | The shepherds. |
| **The Garden** | The summit. | **Ladon.** |

Currency: **drachmae** (dr). Rare currency: **pomegranate seeds**.

### The mountain in twelve bands

Your level is how high you have climbed. Each band has its own creatures, and a
gatekeeper at its upper edge.

| Level | Band | Gatekeeper at the top |
|---|---|---|
| 1 | The Foothills | Myrto's cousin **Agathe**, a goatherd with a staff and no patience |
| 2 | The Olive Terraces | **Old Stavros**, who has pruned these trees for sixty years |
| 3 | The Goat Tracks | **Kleitos Two-Dogs** (the dogs help) |
| 4 | The Pine Belt | **Ione of the Pines**, huntress |
| 5 | The Scree Fields | **Damon and Lykos**, brothers who finish each other's swings |
| 6 | The Cloud Line | **Brother Aither**, a hermit who fights with his eyes shut |
| 7 | The Eagle Crags | **Aella Eagle-Caller** |
| 8 | The Snow Line | **Chione**, daughter of the north wind |
| 9 | The Windgap | **Zetes**, who is rarely on the ground |
| 10 | The Black Stair | **The Warden**, who has not spoken in living memory |
| 11 | The Last Shoulder | **Aigle**, one of the Hesperides, at the garden wall |
| 12 | The Garden Wall | — (Ladon) |

## 3. The climber

One character per BBS account, named by the account's username (no separate
handles: nobody can pose as someone else). No gender is asked or assumed; the
game says "you", and the news says "they".

| Attribute | Notes |
|---|---|
| Level 1–12, XP | XP resets to 0 on each level gained. |
| Hit points / max | Max rises with level. |
| Strength, Defence | Base values from level, plus permanent gifts from seeds. |
| Weapon, Armour | One of each, tiers 1–12. |
| Drachmae in hand / in the Vault | Only coin in hand can be lost. |
| Seeds | Rare. Kept across ascents. |
| Charm | Opens courtship steps, improves some events. Kept across ascents. |
| Calling + rank | §3.1. Kept across ascents. |
| Slope fights / player fights / skill uses left today | Reset at dawn. |
| Alive? Where sleeping? | Room or Camp. |
| Ascents | How many times Ladon has fallen to you. |
| Heart | Spouse or sweetheart, courtship progress, and whether you accept flirting from other players (§10.2). |

A new climber starts at level 1 with an **Olive Branch**, a **Wool Cloak**, and
60 dr. (The simulator showed that starting empty-handed makes the first level
take ten days.)

### 3.1 Callings

Chosen at creation; can be changed at the Shepherds' Fire. Rank runs 0–40, is
earned from rare events and from each gatekeeper beaten, and is never lost.
Uses per day = 1 + rank ÷ 5.

| Calling | Patron | In a fight |
|---|---|---|
| **The Spear** | Ares | **Fury** — one blow at triple damage. |
| **The Torch** | Hecate | **Flame** — a blow at double damage that leaves the enemy scorched, halving its next blow; at rank 10, **Mend** — heal a third of your max HP instead; at rank 20, **Shadow** — slip away from any fight you are allowed to run from, guaranteed. |
| **The Sandal** | Hermes | **Quick Hands** — an ordinary blow that also lifts a quarter again of the enemy's purse (once per fight). Always: you are never ambushed. At rank 10: fleeing never fails. |

## 4. The day

- A day begins at **local midnight** (time zone configurable; default the
  server's).
- Each dawn you get **15 slope fights**, **3 player fights**, your skill uses,
  full hit points, and one visit each to the bard and to courtship.
- Unspent fights do not carry over.
- There is no background job. The first thing any request does is check
  whether the player's last-played day is before today, and if so apply dawn to
  that player. Town-wide dawn work (the Herald's opening line) happens the same
  way on the first request of the day.

**Death.** Killed by a creature or in a duel you started: you lose **all
drachmae in hand** and **10% of your XP toward the next level**, and you are out
until the next dawn. The Vault is untouched. The Herald reports it, kindly or
otherwise. Gatekeeper fights are not to the death (§7.2). Being robbed in your
sleep never costs you a day (§10.1).

**Idle climbers.** Nothing is ever deleted. After 14 days away a climber drops
off the Stele and cannot be attacked, and returns exactly as they left.

## 5. The Slopes

"Climb" spends one slope fight. About one time in eight, instead of a creature,
something else happens (§5.2).

### 5.1 Bestiary

Eight creatures per band, ranked weakest to strongest. A fight picks one at
random from your band. Stats are generated from the band's reference values
(§15) times a rank factor of 0.70 (rank 1) to 1.33 (rank 8), so the whole
bestiary can be retuned by changing a few constants.

| Band | Creatures, weakest first |
|---|---|
| 1 Foothills | Irritable Goat · Olive Thief · Tipsy Satyr · Stray Hound · Road Bandit · Deserter Hoplite · Wild Boar · Overzealous Tax Collector |
| 2 Olive Terraces | Terrace Viper · Mob of Crows · Angry Beekeeper · Grove Poacher · Scarecrow That Moved · Cattle Rustler · Sow with Piglets · Landlord's Bailiff |
| 3 Goat Tracks | Cliff Ram · Pebble Daimon · Goat-Rustling Satyr · Hill Brigand · Mountain Lynx · Mad Hermit · Stymphalian Fledgling · Brigand Captain |
| 4 Pine Belt | Marten Swarm · Scorned Dryad · Feral Charcoal-Burner · Grey Wolf · Lost Maenad · Pair of Wolves · She-Bear · Pack Leader |
| 5 Scree Fields | Scree Scorpion · Bone Picker · Rival Climber · Harpy Chick · Twin Vipers · Cyclops Shepherd-Boy · Sliding Boulder · Harpy |
| 6 Cloud Line | Mist Shade · Cloud-Blind Ox · Echo That Hits Back · Fog Wolf · Storm-Petrel Flock · Ghost of a Lost Legionary · Walking Lightning-Struck Pine · Nephele's Hound |
| 7 Eagle Crags | Crag Eagle · Nest Guardian · Bandit on a Rope · Griffin Fledgling · Archer's Shade · The Talon Twins · Griffin · Aetos the Old Eagle |
| 8 Snow Line | Surprisingly Vicious Hare · Ice Viper · Frostbitten Shade · White Wolf · White Lynx · Frozen Hoplite · Avalanche Spirit · Boreal Giant's Child |
| 9 Windgap | Gale Sprite · Tumbling Harpy · Wind-Mad Pilgrim · Kite-Winged Thief · Hound of the Four Winds · Thunder Ram · Harpy Matron · Shade of the Gap Warden |
| 10 Black Stair | Stair Crawler · Obsidian Asp · Step-Counting Daimon · Black Stair Hound · Shade of a Proud King · Bronze Automaton · Oath-Breaker's Ghost · Automaton Captain |
| 11 Last Shoulder | Titan's Knucklebone · Sleepless Sentinel · Chimera Cub · Sky-Weary Giant · Atlas' Dropped Pebble · Young Chimera · Hundred-Handed Stripling · Chimera |
| 12 Garden Wall | Garden Wasps · Apple Thief · Hesperid's Peacock · Root Serpent · Ladon's Shed Skin · Lesser Head of Ladon · Twin Heads of Ladon · Nymph-Guard of the Tree |

Each creature gets two or three lines of original flavour text and a death line,
written at implementation.

One fight in forty drops a **pomegranate seed**.

### 5.2 Events

All original. Each costs the slope fight that found it.

| Event | What happens |
|---|---|
| **Cold spring** | Full heal. |
| **The boulder** | A great round stone blocks the path, and a tired, cheerful man is leaning on it. Help him push: lose a quarter of your HP, gain a slope fight's worth of XP and something he says. Or go around. On rare days he teaches you something: +1 calling rank. |
| **Persephone's wall** | A pomegranate hangs over an old orchard wall. Take it: a seed — or, one time in four, a furious gardener (a fight, one rank above your band's strongest). |
| **Satyr's wager** | A drinking contest for a stake you choose (up to a day's earnings). Charm tilts the odds. |
| **Lost kid** | A goat kid, bleating. Carry it down to town (+1 Charm, and the Herald mentions it) or sell it (drachmae). |
| **Crossroads shrine** | Leave an offering to Hermes. One in three, he is pleased: +3 slope fights today. |
| **Wild hive** | Reach in: honey (+2 max HP, permanently) or stings (lose a third of your HP; never fatal). |
| **Rockslide** | Lose HP; never fatal. |
| **Wandering oracle** | Tells you one true thing: how far it is to your next gate or, at the wall, what the garden will ask of you. (Intelligence about other climbers lives at the Shepherds' Fire instead, where you can ask about the others. "What Ladon is weak to" was dropped: he has no such weakness to reveal.) |
| **Eagle's gift** | An eagle drops something shiny: drachmae scaled to your band. |
| **Toll-taker** | Pay a small toll, or fight a strong creature for double coin. |
| **Shade of a fallen climber** | Rare. They finish a lesson they were learning when they died: +1 calling rank. |
| **Smoke between the pines** | You find the Shepherds' Fire (§9.5), and know the way from now on. |

## 6. Combat

Turn-based, one action per request: **Attack**, **Skill** (if uses remain),
**Run**.

- `ATK` = Strength + weapon power. `DEF` = Defence + armour power.
- You strike first 70% of the time; otherwise the creature gets an opening blow.
- Your blow: random from ATK÷2 to ATK; one in ten is a **mighty blow**, doubled.
- Its blow: random from its attack÷2 to its attack, minus DEF÷2, minimum 1.
- **Run** works three times in four. When it fails, the creature hits you first.
- Win: XP and drachmae. Lose: §4, Death.

Duels with other climbers use the same rules; the defender is played by the
game, attacks every round, never runs, and uses no skills.

Every outcome is rolled on the server when the action is submitted. Viewing a
page never rolls anything, so reloading cannot change a result.

## 7. Progression

### 7.1 Levels

XP comes only from fights and events. §15 gives the XP needed per level; each
band is tuned to take two to three days of steady play.

### 7.2 Gatekeepers

With enough XP, ask Myrto at the Palaestra to face your band's gatekeeper.

- One attempt per day. You start the fight at whatever HP you have.
- No running, and no dying: lose, and you wake at the Palaestra with 1 HP, your
  purse intact, and an unsolicited critique.
- Win: next level, full heal, +1 calling rank, and the Herald announces it.
- A gatekeeper is the strongest creature of the band with 2.2× the health and
  1.3× the attack. With gear of the band's tier you win roughly four times in
  five, more as you climb; one tier behind on both, a third to a half of the
  time (§15). **Gear matters, and is never a wall.**

### 7.3 Gear

Twelve tiers each, one per band. Trade-in gives half the old item's price. You
may buy at most one tier above your level.

| Tier | Weapon (Brontes' Forge) | Armour (Aegis Row) |
|---|---|---|
| 1 | Olive Branch | Wool Cloak |
| 2 | Shepherd's Crook | Goatskin Jerkin |
| 3 | Bronze Knife | Linen Cuirass |
| 4 | Hunting Spear | Wicker Shield and Greaves |
| 5 | Hoplite's Xiphos | Bronze Bell Cuirass |
| 6 | Boar Lance | Hoplon and Bronze |
| 7 | Labrys | Scale Coat |
| 8 | Thracian Rhomphaia | Helm and Ringmail |
| 9 | Spear of Ash and Iron | Muscled Cuirass |
| 10 | Adamant Sickle | Nemean Hide |
| 11 | Star-Metal Blade | Adamant Plate |
| 12 | Thunder-Scorched Spear | Fragment of the Aegis |

Prices and power: §15.

## 8. Town services

- **House of Hygieia.** Heal any number of hit points, priced per point and
  scaled to your band, so that a full heal costs about **two kills' coin**.
  That is dear enough to make "heal now, or bank it for the spear?" a real
  decision, and no dearer: this price is the most sensitive number in the game
  (§15).
- **The Ferryman's Vault.** Deposit and withdraw, no fees, no interest (interest
  compounds into nonsense over a month; it can be switched on later if the
  economy wants a sink or a faucet).
- **The Orchard Gate.** Two seeds buy one permanent gift: +2 Strength, +2
  Defence, or +5 max HP. Permanent means *across ascents*. These are large in
  the Foothills and negligible at the Garden Wall: they speed the early climb
  of a veteran without trivialising the summit.

## 9. The Lethe House

### 9.1 Orpheus sings

Once a day. He picks one of eight songs; you get its blessing until dawn.

| Song | Blessing |
|---|---|
| The Road Goes Up | +3 slope fights today |
| Bronze and Breath | Healed to full, +10% max HP today |
| What the Ferryman Owes | A purse of drachmae, scaled to your band |
| The Goatherd's Daughter | A slope fight's worth of XP |
| Eurydice, Almost | +1 Charm (rare) |
| Nine Sisters | +1 skill use today |
| A Stone Remembers | Your first fight today cannot kill you |
| (He breaks a string.) | Nothing. He apologises. It happens. |

Lyrics are four original lines each.

### 9.2 The wall

Climbers scratch a line into the tavern wall; the last fifteen show. 120
characters, plain text, the BBS's usual content rules, and admins can remove a
line. This is the game's public conversation.

### 9.3 Company

Two regulars can be courted, by anyone: **Kalliste**, a vintner with a sharp
tongue, and **Theron**, a hunter who is shy everywhere but the hills. One
attempt a day, with one of them at a time. Eight steps, each needing more Charm
than the last:

| Step | | Charm needed |
|---|---|---|
| 1 | Catch their eye | 1 |
| 2 | Stand them a cup of wine | 2 |
| 3 | Trade stories | 4 |
| 4 | Walk by the river | 7 |
| 5 | Bring a gift (costs drachmae) | 10 |
| 6 | Dance at the festival fire | 14 |
| 7 | Meet the family | 19 |
| 8 | Ask | 25 |

Success is likelier the further your Charm exceeds the step. Each success gives
XP and sometimes +1 Charm; a failure costs a little dignity and nothing else.
Married to a regular: a small gift each dawn, and they turn up in your news.
Everything fades to black at "walk by the river".

### 9.4 Rooms, and Nikandros

- **A room for the night** costs about two kills' coin at your band. In a room
  you cannot be robbed. Otherwise you sleep at the Camp. One night's rent covers
  tonight and all of tomorrow and no longer: dawn is applied lazily, and without
  that limit a single night's rent would shelter an absent climber for ever.
- **A cup of wine**: a small heal and a piece of gossip (a hint, or news).
- **A quiet word**: for about twenty kills' coin, Nikandros lends you a key.
  Once, tonight, you may challenge someone who is asleep in a room. Expensive
  on purpose; it exists so that nobody is perfectly safe.

### 9.5 The Shepherds' Fire

Hidden until you stumble on it. **Knucklebones** (a dice game for drachmae,
fair odds, a daily limit), **change your calling** (rank carries over at half),
and **ask about someone** (one climber's level, gear, and where they sleep).

## 10. Other climbers

### 10.1 Robbing the sleeping

- Three attempts a day, from the Camp list.
- A target must be: alive, not in a room (unless you hold a key), not seen in
  the game for ten minutes, not idle 14+ days, not your spouse, not already
  attacked by you today, and **no more than one level below you**. Climbers in
  their first three days cannot be attacked.
- You fight their stats, played by the game (§6).
- **You win:** you take the drachmae they have in hand *when the fight ends*
  (the purse is a real transfer between the two rows, debited before it is
  credited, so banking mid-fight saves the coin and nothing can be duplicated),
  plus XP scaled to their level; they lose 5% of their XP toward the next level. They do *not* lose
  their next day: they wake to a note saying who robbed them, and the Herald
  tells the town.
- **You lose:** you die (§4); they gain XP and your purse.

The defence is ordinary prudence: bank your coin, rent a room.

### 10.2 Courting other climbers

**Opt-in.** Each player chooses whether their character accepts flirtation from
other players; the default is *no*. NPC courtship (§9.3) is unaffected.

- One flirt per day to one open-hearted climber. They are told, and may flirt
  back, ignore it, or **close the door** — which silently blocks further flirts
  from that player. There is no free-text in a flirt; messages go through the
  BBS's own DMs, where the usual rules and moderation already apply.
- Flirts build *affinity* only when they are returned: yours counts only if
  they have flirted back since your last one. One-sided attention never adds
  up to anything. At affinity 5 and Charm 5, either may propose; the other
  must accept.
- **Closing the door is a shadow-block.** The person shut out sees exactly
  what they saw before, their daily flirt is spent as usual, and nothing
  arrives: no note, no affinity, no proposal. Closing the door also withdraws
  any proposal they had made.
- **Married climbers** cannot attack each other, each gets a small dawn bonus
  when the other played yesterday, and either may end it (a Charm penalty, a
  Herald notice, no drama mechanics).
- A climber is courting an NPC or a player, not both.

## 11. Ladon, and the ascent

At level 12, "Seek the Garden" spends a slope fight and starts the fight.

- Ladon has 2.8× your band's reference health and 1.3× the attack of its
  strongest creature. With tier-12 gear it is a coin flip; without it, nearly
  hopeless (§15). Skills, a blessing from Orpheus, and an oracle's hint shift
  the odds — which is why they exist.
- He has a hundred heads; the fight text counts them down.
- No running. Losing is a real death.
- One attempt per day.

**Winning.** You take a golden apple. The Herald makes a fuss. You fall asleep
under the tree and wake that evening in the Foothills, the day's climbing done;
the next dawn is an ordinary first day:

| Kept | Lost |
|---|---|
| Ascent count (+1) and its title | Level and XP |
| Calling and rank | Weapon and armour |
| Charm | Drachmae, in hand *and* in the Vault |
| Seeds, and gifts bought with them | |
| Spouse or sweetheart | |

Each ascent makes the mountain's creatures 3% tougher (health only), up to
+30%. Simulated, a sixth ascent takes about as long as the first.

| Ascents | Title |
|---|---|
| 0 | Climber |
| 1 | Apple-Bearer |
| 2 | Twice-Risen |
| 3 | Thrice-Risen |
| 5 | Stone-Roller |
| 7 | Friend of the Mountain |
| 10 | the Happy |

## 12. The Herald, the Stele, and the BBS

- **The Herald** keeps three days of news: levels gained, deaths, robberies,
  weddings, ascents, kids carried home, plus one line of daily colour.
- **The Stele** ranks active climbers by ascents, then level, then XP, showing
  calling, title, sweetheart, and whether they are in a room, at the Camp, or
  dead until dawn.
- **Sisyphus integration.** The game appears in `/games` beside Mille Bornes.
  It writes a `game_scores` row (game `climb`) on each level gained and, with
  `won = 1`, on each ascent — so playing counts toward the file-access
  "has played a game" rule exactly as Mille Bornes does, and only after a
  player has actually got somewhere.
- Deleting a BBS user removes their climber and their news.

## 13. Interface

Sisyphus already looks like a terminal; the game leans into it.

- One screen at a time: a framed block of monospace text, a status line
  (HP, drachmae, fights left), and a menu of lettered choices —
  `(C)limb  (F)orge  (A)egis Row  (H)ygieia  (V)ault  (L)ethe House …`
- **Every choice is a real button in a real form.** A small static script maps
  keypresses to those buttons, so `C` climbs; without JavaScript you click.
  Nothing inline: the strict Content-Security-Policy stays as it is.
- Colour is CSS classes (`.c-gold`, `.c-blood`, `.c-sky`), never inline style.
- All text is rendered through the existing autoescaping. The only user-written
  text in the game is the tavern wall.
- Works on a phone: the menu wraps and buttons are finger-sized.

## 14. Technical design

```
lib/climb/
    data.py      tables: bands, creatures, gear, songs, events, constants
    rules.py     pure functions: combat rounds, XP, prices, dawn, eligibility.
                 No database, no clock, no globals. Takes a random.Random.
    text.py      all prose, keyed by id. One file to read, review, and rewrite.
    store.py     database access
    scenes.py    which screen a player is on, and which actions it allows
lib/routes/climb_routes.py      GET /games/climb, POST /games/climb/act
frontend/templates/climb/*.html
frontend/static/js/climb.js     hotkeys only
```

**Lessons carried over from Mille Bornes** (whose tests found four bugs the
code review had missed):

- **State lives in the database**, not in memory. Characters last for weeks and
  must survive a restart. Tables: `climb_players`, `climb_fights` (the fight in
  progress), `climb_news`, `climb_wall`, `climb_hearts` (flirts, affinity,
  closed doors), `climb_robberies`, `climb_meta` (town day).
- **Randomness is injected.** Every rule takes a `random.Random`. Tests pass a
  seeded one and assert exact outcomes; nothing has to be stacked by hand.
- **The clock is injected too**, so dawn, idleness, and "not seen for ten
  minutes" are testable without sleeping or monkeypatching.
- **A turn counter defeats replays.** Each player row has a `turn` integer.
  Every form carries it; an action is applied with
  `UPDATE … SET turn = turn + 1 WHERE user_id = ? AND turn = ?`, and if that
  touches no row the request was stale — a double-click, a second tab, the back
  button — and is ignored. This is also what makes the shared database
  connection safe here.
- **Actions are validated against the current scene.** "Buy tier 12" while in a
  fight is not an error to handle; it is simply not in the list.
- **The simulator drives the real rules module** (`python -m lib.climb.sim`),
  and `tests/test_climb_balance.py` asserts the median first ascent stays
  between 25 and 40 days, that every band takes one to five days, that
  gatekeepers and Ladon stay in their intended win-rate windows, and that the
  healing-price cliff is still where the comment says it is — so a well-meant
  tweak cannot quietly break the month-long arc.
- CSRF, sessions, rate limits, and escaping come from the BBS unchanged.

## 15. Balance

Generated by `lib/climb/data.py`. Every table is `base × growth^(level−1)`, so
the whole curve moves by changing two numbers; run `python -m lib.climb.sim` to
see what a change does.

| Level | Max HP | Strength | Defence | XP to next | Ref. XP / kill | Ref. dr / kill |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 24 | 6 | 2 | 244 | 12 | 22 |
| 2 | 34 | 8 | 3 | 525 | 23 | 38 |
| 3 | 48 | 12 | 4 | 1,165 | 46 | 67 |
| 4 | 69 | 16 | 5 | 2,473 | 89 | 118 |
| 5 | 98 | 23 | 8 | 5,266 | 174 | 206 |
| 6 | 139 | 32 | 11 | 11,065 | 338 | 361 |
| 7 | 197 | 45 | 15 | 23,239 | 660 | 632 |
| 8 | 279 | 63 | 21 | 48,500 | 1,287 | 1,106 |
| 9 | 397 | 89 | 30 | 100,756 | 2,509 | 1,935 |
| 10 | 563 | 124 | 41 | 208,553 | 4,892 | 3,387 |
| 11 | 800 | 174 | 58 | 430,302 | 9,540 | 5,927 |
| 12 | 1,136 | 243 | 81 | — | 18,602 | 10,371 |

| Tier | Weapon power | Weapon price | Armour power | Armour price |
|---:|---:|---:|---:|---:|
| 1 | 6 | (start) | 4 | (start) |
| 2 | 9 | 910 | 6 | 770 |
| 3 | 13 | 1,600 | 9 | 1,400 |
| 4 | 19 | 2,800 | 13 | 2,400 |
| 5 | 29 | 4,900 | 19 | 4,200 |
| 6 | 43 | 8,700 | 28 | 7,400 |
| 7 | 63 | 15,000 | 42 | 13,000 |
| 8 | 93 | 27,000 | 62 | 23,000 |
| 9 | 138 | 46,000 | 92 | 39,000 |
| 10 | 204 | 81,000 | 136 | 69,000 |
| 11 | 303 | 140,000 | 202 | 120,000 |
| 12 | 448 | 250,000 | 298 | 210,000 |

(Prices shown rounded to two significant figures, as the game will round them.
A tier costs about a day and a half of its band's earnings.)

**What the simulator says** (300 seeded runs of the real rules, played by the
dull-but-sensible climber described at the top of `lib/climb/sim.py`):

| Measure | Result |
|---|---|
| First ascent | median **33 days**; 8 in 10 finish between 31 and 36; all finish |
| Days per level | 2 for most of levels 1–6, 3 for levels 7–12, 3 more for Ladon |
| Deaths on the way | median 1 |
| Failed gatekeeper attempts | median 5 (the simulated player challenges the moment it has the XP, in whatever gear it owns) |
| Gatekeeper win rate, gear on tier | 76–79% in the low bands, rising to 96% at the top |
| Gatekeeper win rate, one tier behind on both | 28% at the Olive Terraces, rising to 48% |
| Ladon win rate, tier-12 gear / tier-11 gear | 49% / 3% |
| Sixth ascent (creatures +15% health, a few seed gifts) | median 32 days |

The simulated player uses no skills, meets no events, and hears no songs, all of
which help. Expect real first ascents nearer four weeks than five.

**Three things the simulator caught** that were not visible in the tables, and
are the argument for having one:

1. With no starting gear, level 1 took **ten days**: a new climber could not
   afford to heal. Hence the Olive Branch, the Wool Cloak, and 60 dr.
2. Scaling creatures' health *and* attack by 10% per ascent made a sixth ascent
   **impossible**. Hence health only, 3% a time.
3. **The price of healing is a cliff, not a slope.** With a full heal at two
   kills' coin the climb takes about 33 days; at three, 45; at five, *no simulated
   player ever finished*. A plausible-sounding number ("healing should hurt —
   say six kills") would have shipped an unwinnable game. It is pinned at two,
   and the ascent-length test in §14 exists to keep it honest.

## 16. Build plan

| Step | Deliverable | Done when |
|---|---|---|
| 1 ✅ | `data.py`, `rules.py`, and the simulator driving them | **Done 2026-09-20.** Every rule has a test with scripted dice (`tests/test_climb_rules.py`); the balance tests pass (`tests/test_climb_balance.py`). |
| 2 ✅ | Schema, `store.py`, dawn, scenes, the Agora, the Slopes, combat, death, Hygieia, the Vault | **Done 2026-09-20.** A character can be created and can fight, die, heal, bank, and wake tomorrow — through the routes, under test (`tests/test_climb_routes.py`), and by keyboard alone in a real browser under the CSP. |
| 3 ✅ | Forge, Aegis Row, Palaestra and gatekeepers, the Orchard Gate | **Done 2026-09-20.** Level 1 → 12 is playable: a test bot that can see only what the screens offer climbs from the Foothills to the Garden Wall in about a month of game days (`tests/test_climb_town.py`). |
| 4 ✅ | Ladon, ascent and reset, titles, the Stele, `game_scores` | **Done 2026-09-20.** The whole loop closes: a test bot that sees only the screens climbs, kills Ladon, wakes in the Foothills with its calling rank and an ascent to its name, and starts again (`tests/test_climb_summit.py`). **Steps 1–4 are a complete single-player game.** |
| 5 ✅ | The Lethe House: Orpheus, the wall, rooms, Nikandros; the Herald; events | **Done 2026-09-20.** Orpheus' eight songs, the wall (the only player-written text: escaped, no links, five lines a day, sysop can remove), rooms, wine and gossip; the Herald's three days of news; thirteen Slopes events including the man with the boulder; the hidden Shepherds' Fire (knucklebones, change of calling); and both sysop tools. Deferred to step 6, where they have a use: Nikandros' key, and "ask about someone" at the Fire. |
| 6 ✅ | The Camp and robbery; the key | **Done 2026-09-20.** Two-player tests (`tests/test_climb_camp.py`), including the coin-duplication exploit a snapshot purse would have allowed. Also: a mailbox so the victim's note survives dawn, where people sleep on the Stele, and "ask about the others" at the Fire. |
| 7 ✅ | Courtship: the regulars, then other climbers with opt-in and closed doors | **Done 2026-09-20.** Consent rules are tests (`tests/test_climb_hearts.py`): hearts start closed; flirting needs *both* hearts open; a flirt carries no words even if a form sends some; affinity grows only when attention is returned; a closed door is silent to the person shut out; a proposal needs the other to accept, and cannot be accepted for someone no longer free. |
| 8 ✅ | All prose in `text.py`; read-through for tone; hotkeys; phone layout; headless-browser pass under the CSP | **Done 2026-09-20.** The read-through added articles and plural agreement to narration ("The Twin Vipers hit you"), made the news plural-safe, fixed a nonsense Camp description, and found two lines written but never said; a test now fails on any such line. Phone layout: choices stack as 44px buttons, tables scroll inside themselves. All 18 scenes plus the fight and event screens were opened in headless Chromium at 1100px and 375px: none scrolls sideways, none lacks choices, no CSP violations. |

**The game is complete.** Steps 1–4 are a complete single-player game.** |
| 5 ✅ | The Lethe House: Orpheus, the wall, rooms, Nikandros; the Herald; events | **Done 2026-09-20.** Orpheus' eight songs, the wall (the only player-written text: escaped, no links, five lines a day, sysop can remove), rooms, wine and gossip; the Herald's three days of news; thirteen Slopes events including the man with the boulder; the hidden Shepherds' Fire (knucklebones, change of calling); and both sysop tools. Deferred to step 6, where they have a use: Nikandros' key, and "ask about someone" at the Fire. |
| 6 ✅ | The Camp and robbery; the key | **Done 2026-09-20.** Two-player tests (`tests/test_climb_camp.py`), including the coin-duplication exploit a snapshot purse would have allowed. Also: a mailbox so the victim's note survives dawn, where people sleep on the Stele, and "ask about the others" at the Fire. |
| 7 ✅ | Courtship: the regulars, then other climbers with opt-in and closed doors | **Done 2026-09-20.** Consent rules are tests (`tests/test_climb_hearts.py`): hearts start closed; flirting needs *both* hearts open; a flirt carries no words even if a form sends some; affinity grows only when attention is returned; a closed door is silent to the person shut out; a proposal needs the other to accept, and cannot be accepted for someone no longer free. |
| 8 | All prose in `text.py`; read-through for tone; hotkeys; phone layout; headless-browser pass under the CSP | It is fun to read. |

Steps 1–4 are a complete single-player game. Each later step is independently
shippable.

## 17. Review record

Decided by Ted, 2026-09-20:

| # | Question | Decision |
|---|---|---|
| 1 | Player-to-player courtship opt-in, default off? | **Yes.** |
| 2 | Being robbed never costs the victim a day? | **Yes.** |
| 3 | An ascent takes the Vault as well as the purse? | **Yes.** |
| 4 | Midnight by a `SISYPHUS_TZ` setting, defaulting to server local time? | **Yes.** |
| 5 | PG-13, fading to black at the river? | **Yes.** |
| 6 | Credit line? | **Yes, add it** — wording as in §0.3. |
| 7 | Admin tools: remove a wall line, reset a character? | **Yes to both.** |
| 8 | Names? | **Character names are fine.** |

Changed during the build, with the reason:

- **The Torch's Flame** was "damage that ignores the enemy's guard". Creatures
  have no guard, so against everything on the mountain it was an ordinary
  blow. It is now double damage plus a scorch that halves the enemy's next
  blow. Quick Hands was made precise at the same time.
