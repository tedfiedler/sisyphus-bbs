"""Mille Bornes - The classic 1000-mile card race.

A door game for Sisyphus BBS. Play against the computer in this
classic French card game where you race to be the first to travel
exactly 1000 miles.
"""

import random

# ANSI codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
WHITE = "\033[1;37m"
CLEAR = "\033[2J\033[H"

# Hazard -> Remedy
REMEDY_FOR = {
    "Accident": "Repairs",
    "Out of Gas": "Gasoline",
    "Flat Tire": "Spare Tire",
    "Stop": "Roll",
    "Speed Limit": "End of Limit",
}

# Hazard -> Safety
SAFETY_FOR = {
    "Accident": "Driving Ace",
    "Out of Gas": "Extra Tank",
    "Flat Tire": "Puncture-Proof",
    "Stop": "Right of Way",
    "Speed Limit": "Right of Way",
}


class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.miles = 0
        self.rolling = False
        self.hazard = None  # Accident, Out of Gas, Flat Tire, or None
        self.speed_limited = False
        self.safeties = []
        self.coups = 0
        self.count_200 = 0

    @property
    def can_move(self):
        if self.hazard is not None:
            return False
        return self.rolling or "Right of Way" in self.safeties

    def status_text(self):
        if self.hazard:
            return f"{RED}{self.hazard}{RESET}"
        if self.can_move:
            return f"{GREEN}Rolling{RESET}"
        return f"{YELLOW}Stopped{RESET}"

    def speed_text(self):
        if self.speed_limited and "Right of Way" not in self.safeties:
            return f"{RED}Limited{RESET}"
        return f"{DIM}OK{RESET}"


def card_display(card):
    ctype, value = card
    if ctype == "distance":
        return f"{WHITE}{value} mi{RESET}"
    if ctype == "hazard":
        return f"{RED}{value}{RESET}"
    if ctype == "remedy":
        return f"{GREEN}{value}{RESET}"
    if ctype == "safety":
        return f"{YELLOW}{BOLD}{value}{RESET}"
    return str(value)


def card_name(card):
    ctype, value = card
    return f"{value} mi" if ctype == "distance" else value


def build_deck():
    specs = [
        ("distance", 25, 10), ("distance", 50, 10), ("distance", 75, 10),
        ("distance", 100, 12), ("distance", 200, 4),
        ("hazard", "Accident", 3), ("hazard", "Out of Gas", 3),
        ("hazard", "Flat Tire", 3), ("hazard", "Speed Limit", 4),
        ("hazard", "Stop", 5),
        ("remedy", "Repairs", 6), ("remedy", "Gasoline", 6),
        ("remedy", "Spare Tire", 6), ("remedy", "End of Limit", 6),
        ("remedy", "Roll", 14),
        ("safety", "Driving Ace", 1), ("safety", "Extra Tank", 1),
        ("safety", "Puncture-Proof", 1), ("safety", "Right of Way", 1),
    ]
    deck = []
    for ctype, value, count in specs:
        deck.extend([(ctype, value)] * count)
    random.shuffle(deck)
    return deck


def can_play(card, player, opponent):
    ctype, value = card

    if ctype == "safety":
        return True

    if ctype == "distance":
        if not player.can_move:
            return False
        if player.speed_limited and "Right of Way" not in player.safeties and value > 50:
            return False
        if value == 200 and player.count_200 >= 2:
            return False
        if player.miles + value > 1000:
            return False
        return True

    if ctype == "remedy":
        if value == "Roll":
            return (not player.rolling and player.hazard is None
                    and "Right of Way" not in player.safeties)
        if value == "End of Limit":
            return player.speed_limited and "Right of Way" not in player.safeties
        hazard_map = {
            "Repairs": "Accident",
            "Gasoline": "Out of Gas",
            "Spare Tire": "Flat Tire",
        }
        return player.hazard == hazard_map.get(value)

    if ctype == "hazard":
        if value == "Speed Limit":
            return (not opponent.speed_limited
                    and "Right of Way" not in opponent.safeties)
        if value == "Stop":
            return (opponent.can_move
                    and "Right of Way" not in opponent.safeties)
        # Accident, Out of Gas, Flat Tire
        if not opponent.can_move or opponent.hazard is not None:
            return False
        return SAFETY_FOR.get(value) not in opponent.safeties

    return False


def do_play(card, player, opponent):
    """Execute a card play. Returns a description string."""
    ctype, value = card

    if ctype == "safety":
        player.safeties.append(value)
        if value == "Right of Way":
            player.rolling = True
            player.speed_limited = False
        elif value == "Driving Ace" and player.hazard == "Accident":
            player.hazard = None
        elif value == "Extra Tank" and player.hazard == "Out of Gas":
            player.hazard = None
        elif value == "Puncture-Proof" and player.hazard == "Flat Tire":
            player.hazard = None
        return f"plays {card_display(card)}!"

    if ctype == "distance":
        player.miles += value
        if value == 200:
            player.count_200 += 1
        return f"drives {card_display(card)}! ({player.miles} total)"

    if ctype == "remedy":
        if value == "Roll":
            player.rolling = True
            return f"plays {card_display(card)} and starts moving!"
        if value == "End of Limit":
            player.speed_limited = False
            return f"plays {card_display(card)}!"
        player.hazard = None
        player.rolling = False
        return f"plays {card_display(card)} - hazard cleared!"

    if ctype == "hazard":
        if value == "Speed Limit":
            opponent.speed_limited = True
        elif value == "Stop":
            opponent.rolling = False
        else:
            opponent.hazard = value
            opponent.rolling = False
        return f"plays {card_display(card)} on {opponent.name}!"

    return ""


def apply_coup_fourre(target, hazard_name):
    """Undo a hazard and play the matching safety as coup fourre."""
    safety = SAFETY_FOR[hazard_name]
    target.hand.remove(("safety", safety))
    target.safeties.append(safety)
    target.coups += 1
    # Undo hazard effects
    if hazard_name in ("Accident", "Out of Gas", "Flat Tire"):
        target.hazard = None
        target.rolling = True
    elif hazard_name == "Stop":
        target.rolling = True
    elif hazard_name == "Speed Limit":
        target.speed_limited = False
    # Right of Way extra effects
    if safety == "Right of Way":
        target.rolling = True
        target.speed_limited = False


def cpu_choose(cpu, opponent):
    """AI decision. Returns ("play"|"discard", card_index)."""
    playable = [(i, c) for i, c in enumerate(cpu.hand) if can_play(c, cpu, opponent)]

    if not playable:
        return ("discard", _worst_card(cpu, opponent))

    # Play safeties
    for i, c in playable:
        if c[0] == "safety":
            return ("play", i)

    # Fix our hazard
    for i, c in playable:
        if c[0] == "remedy" and c[1] not in ("Roll", "End of Limit"):
            return ("play", i)

    # Play Roll
    for i, c in playable:
        if c == ("remedy", "Roll"):
            return ("play", i)

    # Play distance (highest first)
    dist = [(i, c) for i, c in playable if c[0] == "distance"]
    if dist:
        dist.sort(key=lambda x: x[1][1], reverse=True)
        return ("play", dist[0][0])

    # Play hazards
    for i, c in playable:
        if c[0] == "hazard":
            return ("play", i)

    # End of Limit
    for i, c in playable:
        if c == ("remedy", "End of Limit"):
            return ("play", i)

    return ("play", playable[0][0])


def _worst_card(player, opponent):
    """Find index of least useful card to discard."""
    scores = []
    for i, (ctype, value) in enumerate(player.hand):
        if ctype == "safety":
            s = 1000
        elif ctype == "distance":
            s = value
            if value == 200 and player.count_200 >= 2:
                s = 0
        elif ctype == "remedy":
            s = 50 if can_play(("remedy", value), player, opponent) else 10
        elif ctype == "hazard":
            s = 30 if can_play(("hazard", value), player, opponent) else 0
        else:
            s = 0
        scores.append((s, i))
    scores.sort()
    return scores[0][1]


def calc_score(player, opponent, winner):
    pts = player.miles
    pts += len(player.safeties) * 100
    if len(player.safeties) == 4:
        pts += 700
    pts += player.coups * 300
    if winner == player.name and player.miles == 1000:
        pts += 400
        if player.count_200 == 0:
            pts += 300
        if opponent.miles == 0:
            pts += 500
    return pts


def draw_board(s, human, cpu, deck_size, messages):
    s.write(CLEAR)
    W = 52
    s.writeln(f"{CYAN}{'=' * W}{RESET}")
    s.writeln(f"  {WHITE}{BOLD}MILLE BORNES{RESET}                       {DIM}Deck: {deck_size:>2}{RESET}")
    s.writeln(f"{CYAN}{'=' * W}{RESET}")

    s.writeln(f"  {WHITE}YOU{RESET}: {human.miles:>4} mi  {human.status_text()}  Speed {human.speed_text()}")
    if human.safeties:
        s.writeln(f"    Safeties: {YELLOW}{', '.join(human.safeties)}{RESET}")

    s.writeln(f"  {WHITE}CPU{RESET}: {cpu.miles:>4} mi  {cpu.status_text()}  Speed {cpu.speed_text()}")
    if cpu.safeties:
        s.writeln(f"    Safeties: {YELLOW}{', '.join(cpu.safeties)}{RESET}")

    s.writeln(f"{CYAN}{'-' * W}{RESET}")

    for msg in messages[-3:]:
        s.writeln(f"  {msg}")
    if messages:
        s.writeln(f"{CYAN}{'-' * W}{RESET}")

    s.writeln(f"  {WHITE}Your hand:{RESET}              {DIM}(* = playable){RESET}")
    for i, card in enumerate(human.hand):
        marker = f"{GREEN}*{RESET}" if can_play(card, human, cpu) else " "
        s.writeln(f"   {marker} {CYAN}{i + 1}{RESET}. {card_display(card)}")

    s.writeln(f"{CYAN}{'=' * W}{RESET}")


async def play(session):
    """Main game entry point. Called with a BBSSession instance."""
    s = session

    # Welcome
    s.write(CLEAR)
    s.writeln(f"\r\n{CYAN}{'=' * 52}{RESET}")
    s.writeln(f"  {WHITE}{BOLD}MILLE BORNES{RESET}")
    s.writeln(f"  {DIM}The classic 1000-mile card race{RESET}")
    s.writeln(f"{CYAN}{'=' * 52}{RESET}")
    s.writeln(f"\r\n{DIM}Race to 1000 miles against the computer.{RESET}")
    s.writeln(f"{DIM}Play distance cards to advance, hazards to slow{RESET}")
    s.writeln(f"{DIM}your opponent, and safeties for protection.{RESET}")
    s.writeln(f"\r\n{DIM}You must play {WHITE}Roll{RESET}{DIM} before you can drive.{RESET}")
    s.writeln(f"{DIM}Max two {WHITE}200 mi{RESET}{DIM} cards per game.{RESET}")
    s.writeln(f"{DIM}Speed Limit restricts you to 25 or 50 mi cards.{RESET}")
    s.write(f"\r\n{GREEN}Press any key to deal...{RESET}")
    await s.readkey()

    deck = build_deck()
    human = Player("You")
    cpu = Player("CPU")
    for _ in range(6):
        human.hand.append(deck.pop())
        cpu.hand.append(deck.pop())

    messages = []
    winner = None

    while True:
        # === PLAYER TURN ===
        if not human.hand and not deck:
            pass  # Skip turn
        else:
            if deck:
                human.hand.append(deck.pop())

            if human.hand:
                while True:
                    draw_board(s, human, cpu, len(deck), messages)
                    s.writeln(f"  {DIM}[P]lay card  [D]iscard card  [Q]uit{RESET}")
                    s.write(f"\r\n{GREEN}Action: {RESET}")
                    key = (await s.readkey()).upper()
                    s.writeln(key)

                    if key == "Q":
                        s.writeln(f"\r\n{DIM}Game abandoned.{RESET}")
                        await s.pause()
                        return

                    if key not in ("P", "D"):
                        messages = [f"{RED}Choose [P]lay or [D]iscard.{RESET}"]
                        continue

                    s.write(f"{GREEN}Card # (1-{len(human.hand)}): {RESET}")
                    num_str = await s.readline()
                    if not num_str.strip().isdigit():
                        messages = [f"{RED}Enter a card number.{RESET}"]
                        continue
                    idx = int(num_str.strip()) - 1
                    if idx < 0 or idx >= len(human.hand):
                        messages = [f"{RED}Invalid card number.{RESET}"]
                        continue

                    card = human.hand[idx]

                    if key == "P":
                        if not can_play(card, human, cpu):
                            messages = [f"{RED}Can't play {card_name(card)} right now.{RESET}"]
                            continue
                        human.hand.pop(idx)
                        msg = do_play(card, human, cpu)
                        messages = [f"You {msg}"]

                        # Check coup fourre for CPU
                        if card[0] == "hazard":
                            safety = SAFETY_FOR[card[1]]
                            if ("safety", safety) in cpu.hand:
                                apply_coup_fourre(cpu, card[1])
                                messages.append(
                                    f"{YELLOW}{BOLD}CPU plays Coup Fourre: "
                                    f"{safety}!{RESET}"
                                )
                        break
                    else:
                        human.hand.pop(idx)
                        messages = [f"{DIM}You discard {card_display(card)}.{RESET}"]
                        break

        # Check game end
        if human.miles >= 1000:
            winner = human.name
            break
        if not deck and not human.hand and not cpu.hand:
            break

        # === CPU TURN ===
        if not cpu.hand and not deck:
            pass  # Skip turn
        else:
            if deck:
                cpu.hand.append(deck.pop())

            if cpu.hand:
                action, idx = cpu_choose(cpu, human)
                card = cpu.hand[idx]

                if action == "play":
                    cpu.hand.pop(idx)
                    msg = do_play(card, cpu, human)
                    messages.append(f"CPU {msg}")

                    # Check coup fourre for player
                    if card[0] == "hazard":
                        safety = SAFETY_FOR[card[1]]
                        if ("safety", safety) in human.hand:
                            draw_board(s, human, cpu, len(deck), messages)
                            s.writeln(
                                f"\r\n  {YELLOW}{BOLD}Coup Fourre! "
                                f"Play {safety}? [Y/N]{RESET}"
                            )
                            s.write(f"\r\n{GREEN}Choice: {RESET}")
                            choice = (await s.readkey()).upper()
                            s.writeln(choice)
                            if choice == "Y":
                                apply_coup_fourre(human, card[1])
                                messages.append(
                                    f"{YELLOW}{BOLD}You play Coup Fourre: "
                                    f"{safety}!{RESET}"
                                )
                else:
                    cpu.hand.pop(idx)
                    messages.append(f"{DIM}CPU discards a card.{RESET}")

        # Check game end
        if cpu.miles >= 1000:
            winner = cpu.name
            break
        if not deck and not human.hand and not cpu.hand:
            break

    # === GAME OVER ===
    draw_board(s, human, cpu, len(deck), messages)

    human_score = calc_score(human, cpu, winner)
    cpu_score = calc_score(cpu, human, winner)

    s.writeln(f"  {WHITE}{BOLD}GAME OVER{RESET}")
    s.writeln(f"{CYAN}{'=' * 52}{RESET}")
    if winner:
        s.writeln(f"  {winner} reached 1000 miles!")
    else:
        s.writeln(f"  {DIM}All cards played - no one reached 1000.{RESET}")

    s.writeln(f"\r\n  {WHITE}SCORING{RESET}")
    for label, p, opp in [("You", human, cpu), ("CPU", cpu, human)]:
        s.writeln(f"\r\n  {CYAN}{label}:{RESET}")
        s.writeln(f"    Miles:            {p.miles}")
        if p.safeties:
            s.writeln(f"    Safeties:         {len(p.safeties)} x 100 = {len(p.safeties) * 100}")
        if len(p.safeties) == 4:
            s.writeln(f"    All 4 safeties:   700")
        if p.coups:
            s.writeln(f"    Coup fourre:      {p.coups} x 300 = {p.coups * 300}")
        if winner == p.name and p.miles == 1000:
            s.writeln(f"    Trip complete:    400")
            if p.count_200 == 0:
                s.writeln(f"    Safe trip:        300")
            if opp.miles == 0:
                s.writeln(f"    Shutout:          500")
        total = calc_score(p, opp, winner)
        s.writeln(f"    {WHITE}Total: {total}{RESET}")

    s.writeln(f"\r\n{CYAN}{'-' * 52}{RESET}")
    s.writeln(f"  {WHITE}Final: You {human_score}  -  CPU {cpu_score}{RESET}")
    if human_score > cpu_score:
        s.writeln(f"\r\n  {GREEN}{BOLD}You win!{RESET}")
    elif cpu_score > human_score:
        s.writeln(f"\r\n  {RED}CPU wins!{RESET}")
    else:
        s.writeln(f"\r\n  {YELLOW}It's a tie!{RESET}")

    await s.pause()
