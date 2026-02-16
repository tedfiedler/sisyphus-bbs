"""Mille Bornes - The classic 1000-mile card race.

A door game for Sisyphus BBS. Play against the computer in this
classic French card game where you race to be the first to travel
exactly 1000 miles.
"""

from lib.mille import (
    REMEDY_FOR, SAFETY_FOR, Player,
    card_name, build_deck, can_play, do_play,
    apply_coup_fourre, cpu_choose, calc_score,
)

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


def _status_text(player):
    if player.hazard:
        return f"{RED}{player.hazard}{RESET}"
    if player.can_move:
        return f"{GREEN}Rolling{RESET}"
    return f"{YELLOW}Stopped{RESET}"


def _speed_text(player):
    if player.speed_limited and "Right of Way" not in player.safeties:
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


def draw_board(s, human, cpu, deck_size, messages):
    s.write(CLEAR)
    W = 52
    s.writeln(f"{CYAN}{'=' * W}{RESET}")
    s.writeln(f"  {WHITE}{BOLD}MILLE BORNES{RESET}                       {DIM}Deck: {deck_size:>2}{RESET}")
    s.writeln(f"{CYAN}{'=' * W}{RESET}")

    s.writeln(f"  {WHITE}YOU{RESET}: {human.miles:>4} mi  {_status_text(human)}  Speed {_speed_text(human)}")
    if human.safeties:
        s.writeln(f"    Safeties: {YELLOW}{', '.join(human.safeties)}{RESET}")

    s.writeln(f"  {WHITE}CPU{RESET}: {cpu.miles:>4} mi  {_status_text(cpu)}  Speed {_speed_text(cpu)}")
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
