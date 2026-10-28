#!/usr/bin/env python3
# Run htop in a 200x40 pty for a few seconds, then print each header row followed by its
# text grouped by color, e.g. "[bold yellow]95°C". For checking meter colors, which a
# plain terminal read cannot show. Usage: htop-capture.py <htoprc> <htop binary> [seconds]
import os, pty, re, signal, struct, sys, time, fcntl, termios, select

htoprc, binary = sys.argv[1], sys.argv[2]
seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
ROWS, COLS = 40, 200

pid, fd = pty.fork()
if pid == 0:
    fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
    env = dict(os.environ, TERM="xterm-256color", HTOPRC=htoprc)
    os.execve(binary, [binary], env)

raw = b""
end = time.monotonic() + seconds
while time.monotonic() < end:
    r, _, _ = select.select([fd], [], [], 0.1)
    if r:
        try:
            raw += os.read(fd, 65536)
        except OSError:
            break
os.write(fd, b"q")
time.sleep(0.3)
try:
    os.kill(pid, signal.SIGTERM)
except ProcessLookupError:
    pass
os.waitpid(pid, 0)

# Minimal screen model: cursor moves (CSI row;col H), SGR colors, text. Enough for htop's header.
screen = [[(" ", "")] * COLS for _ in range(ROWS)]
row = col = 0
attr = ""
names = {30: "black", 31: "red", 32: "green", 33: "yellow", 34: "blue", 35: "magenta", 36: "cyan", 37: "white"}
text = raw.decode("utf-8", "replace")
i = 0
token = re.compile(r"\x1b\[([0-9;?]*)([A-Za-z])|\x1b[()][0-9A-B]|\x1b[=>]|\x1b\][^\x07]*\x07|([\r\n\b])|([^\x1b\r\n\b]+)")
for m in token.finditer(text):
    if m.group(2):
        params, cmd = m.group(1), m.group(2)
        nums = [int(p) for p in params.replace("?", "").split(";") if p.isdigit()]
        if cmd == "H":
            row = (nums[0] - 1) if nums else 0
            col = (nums[1] - 1) if len(nums) > 1 else 0
        elif cmd == "m":
            codes = nums or [0]
            parts = set(attr.split()) if attr else set()
            for c in codes:
                if c == 0:
                    parts = set()
                elif c == 1:
                    parts.add("bold")
                elif c in names:
                    parts = {p for p in parts if p not in names.values()}
                    parts.add(names[c])
                elif c == 39:
                    parts = {p for p in parts if p not in names.values()}
            attr = " ".join(sorted(parts))
        elif cmd == "C":
            col += nums[0] if nums else 1
        elif cmd == "D":
            col -= nums[0] if nums else 1
        elif cmd == "A":
            row -= nums[0] if nums else 1
        elif cmd == "B":
            row += nums[0] if nums else 1
        elif cmd == "d":
            row = (nums[0] - 1) if nums else 0
        elif cmd == "X":
            for c in range(col, min(COLS, col + (nums[0] if nums else 1))):
                screen[row][c] = (" ", "")
        elif cmd == "G":
            col = (nums[0] - 1) if nums else 0
        elif cmd == "K":
            for c in range(col, COLS):
                screen[row][c] = (" ", "")
        elif cmd == "J" and (nums or [0])[0] == 2:
            screen = [[(" ", "")] * COLS for _ in range(ROWS)]
    elif m.group(3):
        if m.group(3) == "\r":
            col = 0
        elif m.group(3) == "\n":
            row = min(row + 1, ROWS - 1)
        else:
            col = max(col - 1, 0)
    elif m.group(4):
        for ch in m.group(4):
            if 0 <= row < ROWS and 0 <= col < COLS:
                screen[row][col] = (ch, attr)
            col += 1

for r in range(ROWS):
    line = "".join(ch for ch, _ in screen[r]).rstrip()
    if "PID USER" in line:
        break
    if not line:
        continue
    # group runs of the same attribute
    runs, cur, buf = [], None, ""
    for ch, a in screen[r][:len(line)]:
        if a != cur:
            if buf:
                runs.append((cur, buf))
            cur, buf = a, ""
        buf += ch
    if buf:
        runs.append((cur, buf))
    print(line)
    print("    " + " ".join(f"[{a or 'default'}]{t.strip()}" for a, t in runs if t.strip()))
