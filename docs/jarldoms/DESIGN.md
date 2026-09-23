# The Jarldoms — Design

Status: **draft for review.** Working title; §18 lists alternatives and the
questions the build needs answered. Nothing is built.

A daily-turn empire game for Sisyphus BBS, in the tradition of the BBS door
games of the early 1990s that put every player in charge of a realm and let
them grow it, raid each other, and reckon the score at the end of a round. You
are a jarl with a hold at the head of a fjord. Each day you get a handful of
turns to spend on farms, timber, longhouses, warriors and ships, and on what
you do with them: clear land, trade, send watchers into a neighbour's hall,
or put to sea and raid. At Yule the skald reads the reckoning, one jarl is
named High King, and the round begins again.

The sea is the road. Nobody raids without ships, and nobody who stays home is
ever entirely safe.

---

## 0. Ground rules: this is an original game

These are design constraints, not an afterthought. They hold for every line
written during implementation.

1. **The genre is borrowed; nothing else is.** Daily turn budgets that
   accumulate, a realm of land with buildings on it, population that grows when
   fed and housed, taxes, an army that costs upkeep, attacks whose outcome
   depends on force ratios, spies, pacts, a market, random events, a score, a
   round that ends and resets, and computer-run realms to fill an empty board
   are conventions shared by a whole family of games. Rules and mechanics are
   free for anyone to use.
2. **Every name, every sentence, every number is ours.** Title, setting,
   jarls, holds, units, buildings, events, prose and balance tables are original
   to this project or drawn from Norse history and myth, which are in the public
   domain. No text, name, table or art is reproduced or paraphrased from any
   existing game, from memory or otherwise.
3. **No existing game's name appears in the game.** The credit line, shown on
   the game's title screen, reads: *"In the tradition of the BBS door games of
   the early '90s."*
4. **Numbers are designed, then tested.** The tables in §16 are sized by
   `docs/jarldoms/balance_sim.py` now and will be generated from
   `lib/jarl/data.py` and checked by `lib/jarl/sim.py` once built, which plays
   whole rounds with the real rules; none comes from recollection of anyone
   else's. A test fails if any proper noun from another game appears in the
   code or templates.
5. **Where a familiar convention could be done our own way, it is.** Land is
   *steadings* at the head of a fjord, and the wild beyond them is cleared, not
   bought; the army is a *shield-wall* of huscarls and a levy of farmers; you
   cannot attack without *longships*, and ships have a hold; raids take
   *thralls*; the newspaper is a *saga*; the parliament is the *Thing*; the
   score is *renown*, and it is cut into a stone at Yule.

Tone: dry, saga-flat, PG-13. The skald understates. Violence is the stuff of
the genre and is written the way the sagas write it: a line, not a scene. No
slurs, nothing a sysop would be embarrassed to have on their board.

## 1. Pillars

| Pillar | Meaning |
|---|---|
| **Ten minutes a day** | Twelve turns a day, spent in a few decisions. The turn budget is the pacing and it is what brings people back tomorrow. Unspent turns keep for three days, so a missed evening is not a lost one. |
| **A round is a year, a year is a month** | Thirty days from thaw to Yule. A winner is named, the stone is cut, and everyone starts again with the same forty steadings. |
| **Other jarls are the weather** | Your neighbours' raids, pacts, boasts and betrayals arrive overnight. Five computer-run jarls make sure there is always weather, even on a board of two. |
| **Growing is the game; raiding is the argument** | Land wins rounds. Raiding is how you take what a farmer grew, at the cost of turns you did not spend growing. Both paths must be able to win. |
| **Nobody is erased** | The Thing's peace protects the small. A bad week costs you standing, not the round. |

## 2. The world

**The Nine Fjords**, a coast of the far north: nine fjords cut into the
fells, each with a hold at its head, all facing the same grey sea. Sail is the
only road between them. Behind each hold the wild runs uphill into forest and
fell, and a jarl's realm is as many steadings as have been cleared out of it.

Each player is a jarl with a hold on a fjord. Five fjords are held by
computer-run jarls (§11), so the coast is never empty. The remaining fjords
take players as they arrive; a tenth arrival and beyond gets a fjord "up the
coast" (the world is nine fjords in name, not in code).

Places every jarl knows:

| Place | What it is | Who is there |
|---|---|---|
| **Your hall** | The home screen: your realm's numbers, today's turns, and what happened overnight. | Your steward, **Gunnhild**, who reads the ledger aloud. |
| **The Thing** | The assembly on the headland: pacts, boasts, and the coast's news. | **Eyvind the Skald**, who keeps the Saga. |
| **Saltvik** | The trading booths on the neutral island in the mouth of the fjords. | **Orm Sheep-Rich**, who buys anything and sells most things. |
| **The Stone** | Where Yule's reckoning is cut, round after round. | Nobody. It is a stone. |

## 3. The realm

A realm is land, folk, stores, warriors and ships.

**Land** is counted in **steadings**. Each steading is one of:

| Steading | Gives, each dawn | Notes |
|---|---|---|
| **Farm** | 12 grain | Also houses 10 folk. |
| **Woodland** | 6 timber | Timber builds ships and halls. |
| **Longhouse** | Houses 100 folk | Folk cannot grow past the roofs you have. |
| **Boatyard** | Halves the timber a longship costs | At most one counts. |
| **Wild** | Nothing | Cleared land waiting to be put to a use. |

You start with 40 steadings: 20 farms, 5 woodland, 5 longhouses, 10 wild.

**Folk** pay tax (1 silver a head a day), eat (1 grain per 10 a day), and are
where warriors come from. They grow 5% a day when they are fed and have a
roof, and shrink 6% a day when they starve. A tenth of them will pick up a
spear when the hold is attacked (the **levy**). You start with 400.

**Stores**: **silver** (the coin), **grain** (food), **timber**. Grain and
timber that will not keep is sold to Orm at dawn (§9); silver keeps forever
and counts for renown.

**Warriors**: **huscarls** are the professionals: trained from folk, 15
silver and 5 grain each, 1 silver a day to keep, and they eat three times what
a farmer does. They are worth three levymen in a fight and they are the only
ones who go raiding. The **levy** fights only at home and costs nothing.

**Ships**: **longships**, 60 timber and 40 silver each (half the timber with
a boatyard), 5 silver a day to keep. Each carries 40 huscarls. A raid is as big
as your fleet.

**The palisade** has five levels, 100 silver times the next level, two turns
each. Each level adds a tenth to the strength of everyone defending the hold.

**Honour** starts at 10, cannot go below −50 or above 50, and counts double in
renown (§13). It is the Thing's opinion of you (§8).

## 4. The day and the year

- A day begins at **local midnight** (`SISYPHUS_TZ`, shared with the climb).
- Each dawn: **12 turns** are added, up to a cap of **36**; farms, woodland
  and taxes pay out; folk eat, grow or starve; upkeep is paid; Orm buys the
  surplus; overnight raids and watchers' reports are waiting in the hall.
- There is no background job. The first request a jarl makes checks whether
  their last-played day is before today and applies every missed dawn in
  order. Coast-wide work (the computer-run jarls' turns, the Saga's daily
  line, the market's drift) happens the same way on the first request of the
  day, from whoever makes it.

**The year** is 30 days in three seasons:

| Season | Days | What changes |
|---|---|---|
| **Thaw** | 1–10 | Clearing land costs half. New jarls arrive here without a handicap. |
| **Sailing** | 11–20 | Raids cost 2 turns instead of 3. Thralls are worth more (§6). |
| **Frost** | 21–30 | No land can be cleared; folk eat half again as much; the sea is rough and a raid may be turned back by weather (10%). |

**Yule** is the dawn of day 31. Eyvind reads the reckoning: renown for every
jarl, the **High King** named, the Stone cut. Then every realm is returned to
its first forty steadings and four hundred folk, honour to 10, and the next
year's thaw begins. What survives Yule: your name on the Stone, your count of
crowns, and your standing in the Saga's memory.

**Arriving mid-year.** A jarl who arrives after day 10 starts with the same
realm, plus 12 turns for every day of the year already gone, up to the cap
(so, at most one day's head start in hand). They are under the Thing's peace
(§12) for their first five days.

## 5. The hall

Every action is a button on the hall screen and costs turns. Nothing can be
done that the screen does not offer.

| Action | Turns | Cost | Effect |
|---|---|---|---|
| **Clear land** | 1 | 20 silver × (steadings ÷ 40) | One wild steading. Cheap while you are small; the wild gets harder with every clearing. Half price in thaw; not in frost. |
| **Raise** a farm, woodland, longhouse or boatyard | 1 | 30 silver, 10 timber | On a wild steading. |
| **Pull down** a steading | 0 | nothing | Back to wild. Half the timber comes back. |
| **Train huscarls** | 1 per ten | 15 silver, 5 grain each | From folk; never below 100 folk. |
| **Dismiss huscarls** | 0 | nothing | Back to folk. |
| **Build a longship** | 2 | 60 timber (30 with a boatyard), 40 silver | Carries 40. |
| **Raise the palisade** | 2 | 100 silver × next level | Up to five. |
| **Hold a feast** | 2 | 100 grain, 50 silver | +2 honour, and folk grow 10% tonight instead of 5%. Once a day. |
| **Go to Saltvik** | 1 | — | Trade (§9). |
| **Send watchers** | 1 each | 20 silver each | §7. |
| **Put to sea** | 3 (2 in sailing season) | huscarls and ships | Raid or land-taking (§6). |
| **Go to the Thing** | 0 | — | Pacts, boasts, the Saga (§8). |

Gunnhild's ledger at the top of the hall shows: land by use, folk and roofs,
grain against a day's eating, silver, timber, huscarls and levy, ships and
their hold, palisade, honour, turns, and the day of the year.

## 6. The sea

You choose a jarl to sail against and how many huscarls to send, up to your
fleet's hold. The **shield-wall** you meet is their huscarls, their levy, and
their palisade, at home:

```
attack   = huscarls sent × 3 × luck
defence  = (their huscarls × 3 + their levy × 1) × (1.2 + 0.1 × palisade) × luck
ratio    = attack / defence          luck is 0.9–1.1 for each side
```

**Raid** (3 turns). If the ratio is 1 or better you win: a quarter of their
silver, grain and timber comes home with you, and one in fifty of their folk
as **thralls**, who become your folk (one in thirty in sailing season). You
lose 15% of the huscarls you sent, divided by the ratio; they lose 30% of
theirs and a tenth of the levy. If you lose, you lose 35% of what you sent
and they lose 10% of theirs, and nothing changes hands.

**Land-taking** (4 turns). The same battle, but you need a ratio of **1.5**
to win, and the prize is a tenth of their steadings, which arrive as wild
land of yours (their wild first, then woodland, then farms, then longhouses;
never their last of anything). Land-taking against a realm under the Thing's
peace (§12) is not offered.

Rules of the sea:

- **Three sailings a day, and never the same jarl twice.** A realm cannot be
  bled by one neighbour in an afternoon.
- **A jarl who has not played for three days cannot be sailed against**, and
  their realm stands still until they return (§12).
- **A pact** (§8) takes a jarl off your list of targets until it is broken.
- Battles are settled the moment you sail. The other jarl reads about it at
  their next dawn, in the hall and in the Saga.
- Weather in frost turns a sailing back one time in ten; the turns are spent.

## 7. The watchers

Watchers are the quiet part. Each is a turn and 20 silver, sent against one
jarl, and each succeeds or is caught on a roll weighted by how many watchers
the other jarl keeps at home (a jarl may keep up to ten; each costs 1 silver a
day).

| Errand | On success | If caught |
|---|---|---|
| **Look** | Their ledger, as Gunnhild would read it, in your hall. | They learn you looked. |
| **Burn** | A tenth of their grain. | −2 honour, and the Saga names you. |
| **Steal** | A tenth of their silver, up to 200. | −3 honour, the Saga names you. |
| **Whisper** | Their folk lose 3% tonight; you gain half of them as arrivals. | −3 honour, the Saga names you. |

Success chance: 70%, minus 5% for each watcher they keep, plus 5% for each
you have sent against them today (the first opens the door for the rest).

## 8. The Thing

The assembly, and the only place with player-written words.

- **Pacts.** Offer any jarl a pact; if they accept, neither can sail against
  or send watchers against the other. Either can break it, which the Saga
  reports and which costs the breaker **10 honour**; a broken pact cannot be
  renewed for ten days. A pact with a computer-run jarl is accepted on their
  own terms (§11).
- **Boasts.** One line a day on the boast-wall, 120 characters, no links,
  escaped, the sysop can remove any line. Boasts are what the genre had
  instead of chat, and they are most of its personality.
- **The Saga.** Eyvind keeps three days of coast news: arrivals, raids and
  their outcomes, land taken, pacts made and broken, watchers caught, feasts,
  and one line of daily colour. The dead do not exist here; nobody dies in
  this game, they only lose.
- **Honour** moves as follows. Raid a jarl whose renown is under half of
  yours: −2 ("no glory in it"). Take land from a jarl at half your renown or
  more: +2. Break a pact: −10. Be caught at an errand: as §7. Hold a feast:
  +2. Every ten days with honour above 30: Eyvind sings of you, +1 renown per
  day for the rest of the year. Honour is capped at ±50.

## 9. Saltvik

Orm Sheep-Rich buys and sells grain and timber for silver. Prices start at
0.4 silver a grain and 1.0 a timber and drift a little each day with what the
coast has sold him. Selling a lot in one visit pushes the price down for
everyone by up to a fifth; it recovers over three days. At dawn Orm buys, at
the day's price, any grain beyond five days' eating plus a hundred and any
timber beyond two hundred, whether you visited or not: nothing rots in this
game, it just becomes silver. Huscarls, ships and land cannot be bought here;
only Orm's own stock of them exists, and it is not for sale.

## 10. Events

One day in five, something happens at dawn. Twelve events, weights summing to
100; every one is a single skald's line and a change to the ledger. Examples
of the kinds: a whale beached (grain), a hard frost (folk eat double today),
a wandering skald (honour), a shipwright washed ashore (a free longship if you
have a boatyard), a sickness (folk lose 4%), a good year (farms pay double
today), a landslip (one woodland to wild), a missionary (nothing happens; he
is asked to leave), a stranger who is exactly who he says he is (a hundred
silver and a line in the Saga). The final list is written at implementation,
in `text.py`, with the rest of the prose.

## 11. The five jarls of the coast

Five computer-run realms, each with a habit, so the coast has weather and a
lone player has a game. They take their turns on the first request of each
day, with the same rules and costs as players, and they appear in the Saga
and on the Stone like anyone else.

| Jarl | Habit | What that means |
|---|---|---|
| **Halvard the Grey** | Farmer | Clears, builds, keeps a modest guard. Never sails. Accepts any pact. |
| **Sigrun Oarbreaker** | Raider | Ships and huscarls; raids whoever is richest and undefended, three times a day. Accepts a pact only from a jarl with more huscarls than she has. Breaks it when that stops being true. |
| **Ketil Half-Troll** | Conqueror | Takes land from the weakest defended realm he can beat decisively. Accepts a pact from anyone who has beaten him at home. |
| **Ingirid Salt-Wise** | Turtle | Palisade, huscarls at home, farms. Never sails. Accepts any pact and never breaks one. |
| **Orm Sheep-Rich** | Trader | Runs Saltvik. Has a realm on the neutral island that cannot be sailed against; his renown does not count for the Stone. |

The computer-run jarls obey the same three-sailings rule, the same law's
peace, and lose honour for bullying the same way. They are never allowed to
be the only thing standing between a player and the crown: their renown is
scaled to **90% of the leading player's** at Yule if it would otherwise win.

## 12. Newcomers, the absent, and the small

- **The Thing's peace.** A realm under 30 steadings, or in its first five
  days, cannot be sailed against or have watchers sent against it. It can
  still raid and be raided in the sense of losing a battle it started.
- **The absent.** A jarl who has not played for three days cannot be a
  target; their realm neither grows nor eats until they return, and the dawns
  they missed are applied then, at once, with no raids in them. Nothing is
  deleted, ever. After fourteen days they drop off the Stone's daily standing
  but are still cut into it at Yule if they played that year.
- **Nobody is erased.** Land-taking never takes the last of anything, folk
  never drop below 50 from any cause but starvation, and the peace returns
  the moment a realm falls under 30 steadings.

## 13. Renown, the Stone, and the BBS

```
renown = steadings × 10 + folk ÷ 10 + huscarls + honour × 2 + silver ÷ 50
```

Land is most of it, on purpose: silver must be turned into steadings to win,
and huscarls and hoards are worth something but not a round.

- **The Stone** shows every jarl's renown, land, honour and crowns, updated
  daily, computer-run jarls included and marked as such; and beneath it the
  reckonings of past years: High King, the top three, and the year's Saga
  highlights.
- **Sisyphus integration.** The game appears in `/games` beside the others. It
  writes a `game_scores` row (game `jarl`) each day a jarl plays, with their
  renown, and one with `won = 1` for the High King at Yule, so playing counts
  toward the file-access "has played a game" rule exactly as Mille Bornes and
  the climb do, and only after a successful save.
- **Sysop tools** (admins): remove a boast; reset a jarl; end the year early
  (Yule tomorrow); pause a computer-run jarl.

## 14. Interface

One page, `/games/jarl`, server-rendered, in the site's terminal look.

- **The hall** is the home screen: Gunnhild's ledger in a two-column table,
  the overnight report as a list, and the action buttons. Actions that need a
  number (how many huscarls, how much grain) get a small inline form.
- **Put to sea** shows the jarls you may sail against with what your watchers
  know of them, a picker for huscarls up to your hold, and the choice of raid
  or land-taking.
- **The Thing** is three boxes: pacts (offers in, offers out, standing pacts),
  the boast-wall, the Saga.
- **The Stone** is a table, and above it an **SVG map of the coast**: nine
  fjords as notches in a shoreline, each hold drawn as a longhouse sized by
  its steadings, your own marked, computer-run jarls marked. Built the same
  way as the opening screen's picture, from a generator, with no inline
  styles.
- Hotkeys as in the climb: a letter per button, from a static script over
  real forms. No inline script or style, ever.
- Works on a phone because the tables scroll inside themselves and buttons
  stack; it is not designed for a phone.

## 15. Technical design

```
lib/jarl/
    data.py      tables and constants: costs, yields, seasons, events, jarls
    rules.py     pure functions: dawn, every action, battle, watchers, honour,
                 renown, Yule. No database, no clock, no globals. Takes a
                 random.Random.
    text.py      all prose, keyed by id
    store.py     database access
    scenes.py    which screen a jarl is on and which actions it offers
    npc.py       the five jarls' habits, as functions over rules
    sim.py       plays whole years with rules and npc; balance tests use it
lib/routes/jarl_routes.py       GET /games/jarl, POST /games/jarl/act
frontend/templates/jarl.html
frontend/static/js/jarl.js      hotkeys only
admin/jarl_map.py               the coast map generator (SVG)
```

Carried over from the climb, where each of these earned its place:

- **State lives in the database.** A realm is a JSON document in
  `jarl_realms` with a `turn` counter; a year is a row in `jarl_years`;
  raids, pacts, boasts, watcher reports and Saga lines have tables of their
  own. Realms last a month and must survive restarts.
- **Randomness and the clock are injected.** Tests script the dice.
- **A turn counter defeats replays.** `UPDATE … SET turn = turn + 1 WHERE
  user_id = ? AND turn = ?`; a stale form is ignored.
- **Actions are validated against the current scene.** "Sail against a jarl
  under the peace" is not an error to handle; it is not offered.
- **Cross-realm writes go through `store.change`**, load-mutate-save with a
  retry, one realm at a time, and the loser of a battle is debited before the
  winner is credited, so two colluding jarls cannot duplicate silver (the
  camp in the climb had exactly this hole before its test).
- **Dawns are applied lazily, per realm, in order, and idempotently**, keyed
  on the last day applied, so a jarl who returns after a week gets seven
  dawns and one report.
- **The five jarls and the market are advanced by the first request of the
  day**, under a coast-wide `jarl_years.day` guard, so two simultaneous first
  requests cannot run Sigrun's raids twice.
- **The simulator drives the real rules**, and `tests/test_jarl_balance.py`
  pins the targets in §16.
- CSRF, sessions, rate limits and escaping come from the BBS unchanged. The
  boast-wall is cleaned exactly as the climb's tavern wall is.

## 16. Balance

`docs/jarldoms/balance_sim.py` is a spreadsheet with a loop: four fixed
habits (farmer, raider, conqueror, turtle) play a 30-day year against each
other with the numbers in this document. It is not the game and its jarls do
not adapt, which is its known limit. What it established, in the order the
runs found it:

1. **Tax at half a silver a head starved everything.** Every realm sat at
   zero silver all year and land barely grew. At one silver a head a farmer
   goes from 40 steadings to about 150 in a year, which is the pace wanted.
2. **Grain with no buyer is worthless**, and raids that take grain are then
   pointless. Orm's dawn purchases fixed both.
3. **Honour from raiding inflated renown**: a raider with 125 honour "won"
   with 40 steadings. Raids now pay in loot only; honour comes from taking
   land from equals, feasts, and keeping pacts.
4. **Unlimited raids empty a coast.** One raider sailing a dozen times a day
   took every neighbour to under 100 folk. Three sailings a day, never the
   same jarl twice, and thralls at one in fifty rather than one in twenty.
5. **Land-clearing at two turns made raiding a trap for the raider**: the
   turns spent sailing were turns not spent growing, and loot piled up unspent.
   At one turn a raider who reinvests can keep pace. Whether they can *win*
   against an adaptive farmer is the first thing the real simulator has to
   answer.

Last run, one seed, day 30:

| Jarl | Habit | Land | Folk | Huscarls | Silver | Renown |
|---|---|---:|---:|---:|---:|---:|
| Halvard | farmer | 131 | 102 | 6 | 34 | 1,346 |
| Sigrun | raider | 60 | 789 | 153 | 8,900 | 1,028 |
| Ketil | conqueror | 95 | 129 | 14 | 17 | 1,000 |
| Ingirid | turtle | 69 | 171 | 45 | 2 | 772 |

Over 200 seeds the scripted farmer wins every one, and nobody is erased. The
scripted defenders do not retrain what they lose, which is why their folk
bleed; a player would. **Targets for the real simulator, which the balance
tests will pin:**

- A farmer alone reaches **120–180 steadings** in a year.
- Among adaptive bots, **no habit wins more than 60%** of years.
- A realm keeping huscarls at half its steadings and a level-3 palisade
  **repels a raider of equal renown at least 70%** of the time.
- **Nobody is ever erased**; nobody under the peace ever loses land.
- A jarl who plays every day and one who plays every other day are within
  **a third** of each other's renown at Yule (the turn cap doing its job).

## 17. Build plan

| Step | Deliverable | Done when |
|---|---|---|
| 1 | `data.py`, `rules.py`, `npc.py`, and the simulator driving them | Every rule has a test with scripted dice; the balance tests of §16 pass. |
| 2 | Schema, `store.py`, dawn, the hall and every hall action, Saltvik | A jarl can be created and can clear, build, train, trade, feast, and wake tomorrow, through the routes, under test, and by keyboard in a real browser under the CSP. |
| 3 | The sea: raids, land-taking, the three-sailings rule, the peace; the five jarls taking their turns | Two-player tests, including the silver-duplication case and the peace; a test bot beats Halvard and is beaten by Sigrun. |
| 4 | The Thing: pacts, boasts, the Saga; watchers; events; honour | A year's worth of Saga reads as a story in a test bot's log. **Steps 1–4 are a complete game.** |
| 5 | Yule: the reckoning, the Stone, the reset, `game_scores`, sysop tools | A test bot plays a full year, is crowned, and starts again with its crown on the Stone. |
| 6 | The coast map; all prose in `text.py`; read-through; hotkeys; browser pass | It is fun to read, and the map is worth looking at. |

Each step is independently shippable after step 2.

## 18. Questions for review

1. **Title.** "The Jarldoms" is the working title. Others: *Nine Fjords*,
   *Silver and Salt*, *Yule Reckoning*, *The Long Winter*. Or something else.
2. **Thralls.** Raids taking people is the period, and the word is the
   period's. It is written plainly and without relish. Keep, or make raids
   take only goods?
3. **Round length.** Thirty days, like the climb's first ascent. Shorter years
   mean more Yules and more crowns; longer ones mean more room to come back.
4. **The five jarls.** Five computer-run realms for a board of a handful of
   players. Fewer, more, or none?
5. **Honour caps at ±50** and counts double. Enough of a leash on bullying?
6. **The map.** Worth building in step 6, or leave the Stone as a table?
7. **Consent.** Every jarl is a target from day six; there is no opt-out
   from being raided, because that is the game. The peace, the three-sailings
   rule and the absence rule are the protections. Sufficient?
8. **Federation.** This is the genre that ran inter-board leagues. Nothing
   here depends on it, but if it is ever wanted, a jarl on another board is a
   realm that can be sailed against with a delay. Design for it now (a realm
   has a home board) or not?
