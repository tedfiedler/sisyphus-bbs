"""SSH terminal server for Sisyphus BBS."""

import asyncio
import asyncssh

import config
import auth
import boards
import ansi
from chat import chat_manager
import doors as door_mod
import files as file_mod


class BBSSession:
    """Handles a single terminal user session."""

    def __init__(self, process: asyncssh.SSHServerProcess):
        self.process = process
        self.user: dict | None = None
        self.width = 80
        self.height = 24

    def write(self, text: str):
        self.process.stdout.write(text)

    def writeln(self, text: str = ""):
        self.process.stdout.write(text + "\r\n")

    async def readline(self, echo: bool = True) -> str:
        """Read a line of input from the terminal."""
        buf = []
        while True:
            try:
                data = await asyncio.wait_for(
                    self.process.stdin.read(1), timeout=300
                )
            except asyncio.TimeoutError:
                self.writeln("\r\nSession timed out.")
                return ""
            if not data:
                return ""
            for ch in data:
                if ch in ("\r", "\n"):
                    self.write("\r\n")
                    return "".join(buf)
                elif ch in ("\x7f", "\x08"):  # backspace
                    if buf:
                        buf.pop()
                        self.write("\x08 \x08")
                elif ch == "\x03":  # ctrl-c
                    return ""
                elif ord(ch) >= 32:
                    buf.append(ch)
                    if echo:
                        self.write(ch)
                    else:
                        self.write("*")

    async def readkey(self) -> str:
        """Read a single keypress."""
        try:
            data = await asyncio.wait_for(
                self.process.stdin.read(1), timeout=300
            )
        except asyncio.TimeoutError:
            return ""
        return data if data else ""

    async def pause(self):
        self.write(f"\r\n{ansi.DIM}Press any key to continue...{ansi.RESET}")
        await self.readkey()

    async def run(self):
        """Main session loop."""
        self.write(ansi.CLEAR)
        self.write(ansi.load_ansi("welcome"))
        self.writeln()

        if not await self.login_screen():
            self.writeln("Goodbye!")
            return

        await self.main_menu()

    async def login_screen(self) -> bool:
        """Login or register screen. Returns True if authenticated."""
        for _ in range(3):
            self.writeln(f"{ansi.CYAN}[L]{ansi.RESET} Login  {ansi.CYAN}[R]{ansi.RESET} Register  {ansi.CYAN}[Q]{ansi.RESET} Quit")
            self.write(ansi.prompt("Choice"))
            choice = (await self.readkey()).upper()
            self.writeln(choice)

            if choice == "Q":
                return False
            elif choice == "L":
                self.write(ansi.prompt("Username"))
                username = await self.readline()
                self.write(ansi.prompt("Password"))
                password = await self.readline(echo=False)
                user = await auth.authenticate(username, password)
                if user:
                    self.user = user
                    self.writeln(ansi.success(f"\r\nWelcome back, {user['username']}!"))
                    return True
                self.writeln(ansi.error("\r\nInvalid credentials."))
            elif choice == "R":
                self.write(ansi.prompt("Choose username"))
                username = await self.readline()
                self.write(ansi.prompt("Choose password"))
                password = await self.readline(echo=False)
                result = await auth.register_user(username, password)
                if result:
                    self.user = await auth.authenticate(username, password)
                    self.writeln(ansi.success(f"\r\nAccount created! Welcome, {username}!"))
                    return True
                self.writeln(ansi.error("\r\nUsername already taken."))
        return False

    async def main_menu(self):
        """Main BBS menu loop."""
        while True:
            self.write(ansi.CLEAR)
            self.write(ansi.load_ansi("menu"))
            self.write(ansi.prompt("Command"))
            key = (await self.readkey()).upper()
            self.writeln(key)

            if key == "B":
                await self.boards_menu()
            elif key == "F":
                await self.files_menu()
            elif key == "C":
                await self.chat_screen()
            elif key == "D":
                await self.doors_menu()
            elif key == "W":
                await self.who_online()
            elif key == "Q":
                self.writeln(ansi.success("\r\nThanks for visiting Sisyphus BBS!"))
                return

    async def boards_menu(self):
        """Message board browsing."""
        while True:
            self.write(ansi.CLEAR)
            board_list = await boards.list_boards()
            lines = []
            for i, b in enumerate(board_list, 1):
                lines.append(f"{ansi.YELLOW}{i:>3}{ansi.RESET}. {b['name']:<30} {ansi.DIM}{b['thread_count']} threads{ansi.RESET}")
            self.writeln(ansi.box("MESSAGE BOARDS", lines))
            self.writeln(f"\r\n  {ansi.DIM}Enter # to browse, [N]ew board, [Q]uit{ansi.RESET}")
            self.write(ansi.prompt("Board"))
            line = await self.readline()
            line = line.strip().upper()

            if line == "Q":
                return
            elif line == "N":
                self.write(ansi.prompt("Board name"))
                name = await self.readline()
                self.write(ansi.prompt("Description"))
                desc = await self.readline()
                if name:
                    await boards.create_board(name, desc)
                    self.writeln(ansi.success("Board created!"))
                    await asyncio.sleep(0.5)
            elif line.isdigit():
                idx = int(line) - 1
                if 0 <= idx < len(board_list):
                    await self.thread_list(board_list[idx])

    async def thread_list(self, board: dict):
        """Thread listing for a board."""
        while True:
            self.write(ansi.CLEAR)
            thread_list = await boards.list_threads(board["id"])
            lines = []
            for i, t in enumerate(thread_list, 1):
                prefix = ""
                if t.get("pinned"):
                    prefix = f"{ansi.RED}*{ansi.RESET}"
                lines.append(
                    f"{ansi.YELLOW}{i:>3}{ansi.RESET}. {prefix}{t['subject']:<35} {ansi.DIM}{t['author_name']}  ({t['post_count']} posts){ansi.RESET}"
                )
            if not lines:
                lines.append(f"{ansi.DIM}No threads yet.{ansi.RESET}")

            self.writeln(ansi.box(board["name"], lines))
            self.writeln(f"\r\n  {ansi.DIM}Enter # to read, [N]ew thread, [Q]uit{ansi.RESET}")
            self.write(ansi.prompt("Thread"))
            line = await self.readline()
            line = line.strip().upper()

            if line == "Q":
                return
            elif line == "N":
                self.write(ansi.prompt("Subject"))
                subject = await self.readline()
                self.writeln("Enter message (blank line to end):")
                body_lines = []
                while True:
                    l = await self.readline()
                    if not l:
                        break
                    body_lines.append(l)
                if subject and body_lines:
                    await boards.create_thread(board["id"], subject, self.user["id"], "\n".join(body_lines))
                    self.writeln(ansi.success("Thread created!"))
                    await asyncio.sleep(0.5)
            elif line.isdigit():
                idx = int(line) - 1
                if 0 <= idx < len(thread_list):
                    await self.view_thread(thread_list[idx])

    async def view_thread(self, thread: dict):
        """View posts in a thread."""
        self.write(ansi.CLEAR)
        self.writeln(ansi.header(thread["subject"]))
        post_list = await boards.list_posts(thread["id"])
        for p in post_list:
            self.writeln(f"{ansi.CYAN}┌─ {ansi.WHITE}{p['author_name']}{ansi.RESET} {ansi.DIM}{p['created_at']}{ansi.RESET}")
            for line in p["body"].split("\n"):
                self.writeln(f"{ansi.CYAN}│{ansi.RESET} {line}")
            self.writeln(f"{ansi.CYAN}└{'─' * 40}{ansi.RESET}")

        if not thread.get("locked"):
            self.writeln(f"\r\n  {ansi.DIM}[R]eply  [Q]uit{ansi.RESET}")
            self.write(ansi.prompt("Action"))
            key = (await self.readkey()).upper()
            self.writeln(key)
            if key == "R":
                self.writeln("Enter reply (blank line to end):")
                body_lines = []
                while True:
                    l = await self.readline()
                    if not l:
                        break
                    body_lines.append(l)
                if body_lines:
                    await boards.create_post(thread["id"], self.user["id"], "\n".join(body_lines))
                    self.writeln(ansi.success("Reply posted!"))
                    await asyncio.sleep(0.5)
        else:
            await self.pause()

    async def files_menu(self):
        """File area browser."""
        self.write(ansi.CLEAR)
        file_list = await file_mod.list_files()
        lines = []
        for f in file_list:
            size = f"{f['size_bytes'] / 1024:.1f}K"
            lines.append(
                f"  {f['filename']:<25} {size:>8}  {ansi.DIM}{f['uploader_name']}{ansi.RESET}"
            )
        if not lines:
            lines.append(f"{ansi.DIM}No files uploaded yet.{ansi.RESET}")
        self.writeln(ansi.box("FILE AREAS", lines))
        self.writeln(f"\r\n  {ansi.DIM}Files can be uploaded via the web interface.{ansi.RESET}")
        await self.pause()

    async def chat_screen(self):
        """Real-time chat in terminal."""
        self.write(ansi.CLEAR)
        self.writeln(ansi.header("Chat - #lobby"))
        self.writeln(f"{ansi.DIM}Type messages and press Enter. Type /quit to exit.{ansi.RESET}\r\n")

        channel = "lobby"
        queue = chat_manager.subscribe(channel)

        # Show recent
        recent = await chat_manager.recent_messages(channel, 20)
        for msg in recent:
            self.writeln(f"  {ansi.CYAN}<{msg['username']}>{ansi.RESET} {msg['message']}")

        async def recv_messages():
            try:
                while True:
                    msg = await queue.get()
                    self.writeln(f"\r  {ansi.CYAN}<{msg['username']}>{ansi.RESET} {msg['message']}")
                    self.write(ansi.prompt("Chat"))
            except asyncio.CancelledError:
                pass

        recv_task = asyncio.create_task(recv_messages())
        try:
            while True:
                self.write(ansi.prompt("Chat"))
                line = await self.readline()
                if line.strip().lower() == "/quit":
                    break
                if line.strip():
                    await chat_manager.broadcast(channel, self.user["username"], line.strip())
        finally:
            recv_task.cancel()
            chat_manager.unsubscribe(channel, queue)

    async def doors_menu(self):
        """Door games menu."""
        self.write(ansi.CLEAR)
        door_list = await door_mod.list_doors()
        if not door_list:
            self.writeln(ansi.box("DOOR GAMES", [f"{ansi.DIM}No door games configured.{ansi.RESET}"]))
            self.writeln(f"\r\n{ansi.DIM}Add games to the doors/ directory with a door.cfg file.{ansi.RESET}")
            await self.pause()
            return

        lines = []
        for i, d in enumerate(door_list, 1):
            lines.append(f"{ansi.YELLOW}{i:>3}{ansi.RESET}. {d['name']:<30} {ansi.DIM}{d['description']}{ansi.RESET}")
        self.writeln(ansi.box("DOOR GAMES", lines))
        self.write(ansi.prompt("Door #"))
        line = await self.readline()
        if line.strip().isdigit():
            idx = int(line.strip()) - 1
            if 0 <= idx < len(door_list):
                self.writeln(f"\r\nLaunching {door_list[idx]['name']}...")
                await door_mod.launch_door(
                    door_list[idx]["id"],
                    self.user["id"],
                    self.user["username"],
                )
                await self.pause()

    async def who_online(self):
        """Show who's connected (simplified)."""
        self.write(ansi.CLEAR)
        lines = [
            f"  {ansi.WHITE}{self.user['username']}{ansi.RESET} {ansi.DIM}(you){ansi.RESET}",
        ]
        self.writeln(ansi.box("WHO'S ONLINE", lines))
        await self.pause()


class BBSServer(asyncssh.SSHServer):
    def connection_made(self, conn):
        self._conn = conn

    def begin_auth(self, username):
        # Allow all connections through to the BBS login screen
        return False

    def password_auth_supported(self):
        return True

    async def validate_password(self, username, password):
        # Accept any password - real auth happens in the BBS
        return True


async def handle_client(process: asyncssh.SSHServerProcess):
    session = BBSSession(process)
    try:
        await session.run()
    except (asyncssh.BreakReceived, asyncssh.TerminalSizeChanged, Exception):
        pass
    finally:
        process.exit(0)


async def start_ssh_server():
    """Start the SSH server."""
    # Generate host key if needed
    key_path = config.SSH_HOST_KEY
    try:
        await asyncssh.create_server(
            BBSServer,
            config.SSH_HOST,
            config.SSH_PORT,
            server_host_keys=[key_path],
            process_factory=handle_client,
        )
    except FileNotFoundError:
        # Generate a host key
        key = asyncssh.generate_private_key("ssh-rsa", key_size=2048)
        key.write_private_key(key_path)
        await asyncssh.create_server(
            BBSServer,
            config.SSH_HOST,
            config.SSH_PORT,
            server_host_keys=[key_path],
            process_factory=handle_client,
        )
    print(f"SSH server listening on {config.SSH_HOST}:{config.SSH_PORT}")
