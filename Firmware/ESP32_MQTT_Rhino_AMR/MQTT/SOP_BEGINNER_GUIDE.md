# How to control a Reeman forklift from your computer — Beginner SOP

**Read this first (plain English):**
You are going to make a **robot forklift** do things by sending it messages from a
**Windows computer** over Wi‑Fi. Think of it like a group chat: your computer and
the forklift both join the same chat room, and when your computer posts the right
message, the forklift does the job (drive somewhere, pick up a pallet, drop it).

No prior coding needed. Just follow the steps in order. Each step ends with a
**✅ Check** — don't move on until the check passes.

> Time needed: about 45–60 minutes the first time.

---

## The words you'll see (mini dictionary)

- **MQTT** – the "group chat" system robots use to send short messages.
- **Broker** – the chat server everyone connects to. We run our own using a free
  program called **Mosquitto**. Your computer becomes the chat server.
- **Topic** – a channel name inside the chat, like `.../task/auto_model`.
- **Hostname** – the forklift's name (its username in the chat).
- **Token** – a secret password the forklift gives you so it knows messages are
  really from you.
- **Encryption key** – a secret code word used to scramble the important messages
  so outsiders can't read them. (The program handles the scrambling for you.)
- **IP address** – the "phone number" of a device on the network, like
  `192.168.68.61`.
- **Heartbeat** – your computer saying "I'm still here!" every few seconds. If it
  stops, the forklift ignores you (a safety feature).
- **Client** – the small program (`reeman_forklift_client.py`) you run to talk to
  the forklift.

> 📌 Throughout this guide, values like `rbot55f-260114-003-001`, `a5F6dmfr`,
> `192.168.68.61` are **examples from one specific robot**. **Yours will be
> different.** Wherever you see them, use YOUR robot's values.

---

## What you need before you start

- [ ] A Windows 10/11 computer.
- [ ] The forklift powered on, with its screen showing.
- [ ] A Wi‑Fi network the forklift is connected to (you'll connect your computer
      to the **same** Wi‑Fi).
- [ ] The project folder `reeman-forklift-mqtt` (contains the client program and
      the broker config).
- [ ] An adult / trained operator present whenever the forklift moves. **A forklift
      is heavy machinery. Safety section is at the bottom — read it before moving
      anything.**

---

# PART A — Set up your computer (one time only)

### Step A1 — Install Python
Python is the language our program is written in.
1. Go to https://www.python.org/downloads/ and click the big **Download Python**
   button.
2. Run the installer. **IMPORTANT:** on the first screen, tick the box
   **"Add Python to PATH"**, then click **Install Now**.
3. Open the **Start menu**, type `PowerShell`, and open it. Type:
   ```powershell
   python --version
   ```
   **✅ Check:** it prints something like `Python 3.12.x`.

### Step A2 — Install the helper libraries
These are add-ons our program needs (one talks MQTT, one does the secret-code
scrambling). In the same PowerShell window:
```powershell
cd "D:\Maulik\reeman-forklift-mqtt"
pip install -r requirements.txt
```
**✅ Check:** it finishes with no red error text.

### Step A3 — Install Mosquitto (your chat server)
1. Go to https://mosquitto.org/download/ and download the **Windows** installer.
2. Run it, keep clicking Next (defaults are fine). It installs to
   `C:\Program Files\mosquitto\`.

**✅ Check:** that folder now contains `mosquitto.exe`.

### Step A4 — Open the firewall (let the forklift reach your computer)
The forklift needs to connect *into* your computer, so Windows must allow it.
1. Open the Start menu, type `PowerShell`, **right‑click it → Run as
   administrator**.
2. Paste this and press Enter:
   ```powershell
   New-NetFirewallRule -DisplayName "Mosquitto 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow
   ```
**✅ Check:** it prints a block of text that includes `Enabled : True`.

> You only do Part A once. Next time you start at Part B.

---

# PART B — Start your chat server (the broker)

1. Open a normal PowerShell window (not admin).
2. Start Mosquitto with our settings file:
   ```powershell
   cd "D:\Maulik\reeman-forklift-mqtt\broker"
   & "C:\Program Files\mosquitto\mosquitto.exe" -c "mosquitto.conf" -v
   ```
**✅ Check:** it prints lines ending with
`Opening ipv4 listen socket on port 1883` and then
`mosquitto version ... running`, and then it just sits there.

> ⚠️ **Leave this window open the whole time.** It is your chat server. If you
> close it, the forklift can't talk to you. Open a **new** PowerShell window for
> the next steps.

---

# PART C — Connect the forklift to your chat server

### Step C1 — Get the forklift's secret info
On the forklift's screen, open the screen that shows **pairing / MQTT info**
(ask the supplier where it is if unsure). Write down these three things:

| What | Example | Yours |
|---|---|---|
| **Hostname** (its name) | `rbot55f-260114-003-001` | __________ |
| **Encryption Key** | `a5F6dmfr` | __________ |
| **Token** (long password) | `Z2IcM93div5z...` | __________ |

> The token is long and may contain `/` and `+`. Copy it **exactly**. If the robot
> has a **"Generate Token"** button and you press it, the token changes — write
> down the new one and use that.

### Step C2 — Find your computer's IP address
Your computer needs to be on the **same Wi‑Fi as the forklift**. Connect to it,
then in PowerShell:
```powershell
ipconfig
```
Look under **Wireless LAN adapter Wi‑Fi** for the line **IPv4 Address**, e.g.
`192.168.68.61`. Write it down — this is **YOUR_PC_IP**.

> Both the forklift and your computer should have IPs that start with the same
> first three numbers (e.g. both `192.168.68.x`). If they don't, you're on
> different networks — fix that first.

### Step C3 — Point the forklift at your computer
On the forklift's **MQTT Configuration** screen, type in:

| Field | What to put |
|---|---|
| Server Address (Host) | **YOUR_PC_IP** (e.g. `192.168.68.61`) |
| Port | `1883` |
| Username | leave empty |
| Password | leave empty |
| Encryption Key | leave as it is (e.g. `a5F6dmfr`) |
| Token | leave as it is |

Press **Save**, then turn the connection **On** (or tap Connect).

**✅ Check:** look at your **Mosquitto window** (Part B). Within a few seconds a
new line appears:
`New client connected from <forklift-ip> ...`
🎉 The forklift is now in your chat server.

---

# PART D — Talk to the forklift (no movement yet, totally safe)

### Step D1 — See the forklift's heartbeat (live status)
In a **new** PowerShell window, run this (replace the capital words with YOUR
values from Step C1/C2):
```powershell
cd "D:\Maulik\reeman-forklift-mqtt"
python reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY
```
*(Keep the quote marks around the token.)*

**✅ Check:** every 5 seconds you see a line like:
```
STATUS  battery=53% eStop=1 charge=1 nav=False exec=False lifting=False ...
```
A real battery percentage = **everything works.** 🎉

What the words mean:
- `battery` – charge left (%).
- `eStop=1` – emergency stop is **released / ready** (`0` would mean pressed).
- `nav=True` – it's driving. `exec=True` – it's doing a task.
  `lifting=True` – forks are moving.

To stop the program later, press **Ctrl + C** in its window.

### Step D2 — Ask the forklift for its list of points
Stop the program (Ctrl+C), then run the same command but add `--request-points`:
```powershell
python reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY --request-points
```
**✅ Check:** you see a `POINTS[auto_model] ...` line listing place names like
`mon1, mon21, fri01, ...`. These are the spots the forklift knows how to drive to.
Also note the long **map** name (e.g. `33efb2bef5a6fd69e4282cdb45ff9fea`) — you'll
need it next. Call it **YOUR_MAP**.

---

# PART E — Make the forklift move ⚠️ (read the SAFETY section first!)

> 🚨 From here the machine physically moves. Do **not** continue alone. Clear the
> area, keep a hand near the emergency stop, and read **SAFETY RULES** at the
> bottom.

### Step E1 — Send one pick‑and‑drop job
This tells it: go to `mon1`, pick the pallet, carry it to `mon21`, drop it.
```powershell
python reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY --map YOUR_MAP --pick mon1 --drop mon21
```
- **Keep this window open** and do **not** press Ctrl+C — the forklift needs your
  heartbeat to keep going.
- If a **"Auto mode task received"** message pops up on the forklift screen, it
  will start on its own after a short countdown.

**✅ Check:** the STATUS line changes to `nav=True`, then `task=mon1`, the forklift
drives and the forks lift, then it goes to `mon21`.

### Step E2 — Send several jobs in a row (a route)
```powershell
python reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY --map YOUR_MAP --route "mon1:mon21,fri01:fri11"
```
**✅ Check:** the STATUS line shows `queue=2`, and the count goes down as each job
finishes.

🎉 **That's the whole thing.** You are now commanding a forklift over your own
network.

---

# 🚨 SAFETY RULES (most important page)

1. **Never run a movement command unless the area is clear** of people, pets, and
   obstacles — along the *whole* path, not just the start.
2. **Always have a trained person standing by the physical emergency‑stop button**
   with their hand ready, every single time it moves.
3. **Start small.** Use close points for the first tests. Watch it complete one job
   before trying routes.
4. **The MQTT system has no remote "stop" button.** To stop a moving forklift you
   must press the **physical e‑stop** or use the robot's own screen. Know where the
   e‑stop is before you send any command.
5. **Keep the client program running** during a task. If it closes, the forklift
   may stop or behave unexpectedly.
6. **If anything looks wrong, hit the e‑stop first, ask questions later.**

---

# When something goes wrong (troubleshooting)

| What you see | What it means | What to do |
|---|---|---|
| Mosquitto won't start | Wrong path, or already running | Check `mosquitto.exe` exists in `C:\Program Files\mosquitto\`; close other Mosquitto windows |
| No "New client connected" in Mosquitto | Forklift can't reach your computer | Check both are on the **same Wi‑Fi**; check `Host` on the forklift = YOUR_PC_IP; redo the firewall step (A4) |
| `not authorized` when the client connects | Broker wants a login | Add `--mqtt-user ""` to the command (forces no login) |
| Client connects but no STATUS lines | Forklift isn't sending status | Make sure the forklift's MQTT connection is **On**; check the token is exact |
| `Failed to decrypt` on points | Wrong encryption key | Make sure `--key` matches the **Encryption Key** on the forklift exactly |
| Task sent but forklift doesn't move | It may be waiting, in the wrong mode, or not localized | Watch the forklift screen for a popup; make sure it's in **Auto mode**; if it can't drive even from its own screen, use **Relocation** on the robot to fix its position |
| Your computer's IP changed | Wi‑Fi gave a new address | Run `ipconfig` again, update `--broker` and the forklift's Host to the new IP |

---

# Cheat sheet (all commands in one place)

```powershell
# 1) Start the broker (leave open)
cd "D:\Maulik\reeman-forklift-mqtt\broker"
& "C:\Program Files\mosquitto\mosquitto.exe" -c "mosquitto.conf" -v

# 2) In a new window: watch live status
cd "D:\Maulik\reeman-forklift-mqtt"
python reeman_forklift_client.py --broker YOUR_PC_IP --broker-port 1883 --hostname YOUR_HOSTNAME --token "YOUR_TOKEN" --key YOUR_KEY

# 3) Ask for the list of points
#    ...same as above... --request-points

# 4) One pick -> drop  (MOVES THE FORKLIFT)
#    ...same as above... --map YOUR_MAP --pick mon1 --drop mon21

# 5) Multiple jobs     (MOVES THE FORKLIFT)
#    ...same as above... --map YOUR_MAP --route "mon1:mon21,fri01:fri11"
```

**Replace these with your robot's real values everywhere:**
`YOUR_PC_IP`, `YOUR_HOSTNAME`, `YOUR_TOKEN`, `YOUR_KEY`, `YOUR_MAP`.
