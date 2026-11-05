# ViewSonic ViewBoard for Home Assistant

Control ViewSonic ViewBoard interactive displays (tested on an IFP7550-3) over the network,
using the board's built-in LAN control port (TCP 5000). Each board is added by IP address
and shows up as its own device.

## Install

**Manually:** copy the `custom_components/viewsonic_viewboard` folder into your Home Assistant
`config/custom_components/` folder (create it if it doesn't exist), then restart Home Assistant.

**With HACS:** in HACS choose
*⋮ → Custom repositories*, paste `https://github.com/reberhardtnjsp/viewsonic-viewboard`, pick type *Integration*, and install.
Restart Home Assistant.

## Add a board

*Settings → Devices & services → Add integration → ViewSonic ViewBoard*, then enter the IP
address and, optionally, a name such as "Room 112". Repeat for each board.

## When a board's IP address changes

Boards are identified by MAC address; the IP is only their last-known address. If a board stops
answering there, or a different board answers at that address, the integration searches the
network for its MAC and updates the address on its own. Entities and automations keep working.

How the search works:

1. It looks in Home Assistant's ARP cache, the host's list of which hardware address is at which IP (instant).
2. Otherwise it sweeps the network: the subnet(s) Home Assistant is on, the /24 around every added
   board's last address, and any networks listed in a board's options (see below). Each device with
   port 5000 open is asked for the MAC it reports, which also works through a router. This takes about
   10–20 seconds for a /22. One sweep is shared by all boards, so many boards moving at once (for
   example after a network outage) cost a single scan.

An unreachable board is searched for at most once every 2 minutes. To search right away, press the
board's **Search network for board** button (under Diagnostic). The **IP address** sensor shows the
board's current address, and a warning such as "ViewBoard Room 112 moved from 10.3.12.80 to
10.3.12.78" is written to the Home Assistant log whenever a board is found at a new address.

### Boards on a different network from Home Assistant

If Home Assistant is on a different network from the boards (for example Home Assistant at
192.168.100.50 and the boards on 10.3.12.0/22), tell it where the boards are: open any ViewBoard's
entry, choose **Configure**, and enter the boards' network, such as `10.3.12.0/22`. Separate several
with commas. Networks set on one board are searched for every board, so you only need to set this once.
Without it, only the /24 around each board's old address is searched, so a board that moves from
10.3.12.x to 10.3.13.x might not be found.

Limitations:

- Only private networks of at most 4,096 addresses (a /20) each are searched, never public addresses.
- A board that is off, unplugged or asleep with networking off can't be found until it's back.
- Home Assistant needs the "network" integration (part of a default install) to know its subnets.

You can still change an address by hand: open the board's entry, choose *⋮ → Reconfigure*, and enter
the new address.

## What you get for each board

| Entity | Type | Notes |
|---|---|---|
| *(board name)* | Media player | Power, volume, mute, input, in one card |
| Power | Switch | Turning on also sends Wake-on-LAN |
| Mute | Switch | |
| Screen | Switch | Turns the backlight off/on while the board stays on |
| Input | Select | HDMI 1–4, DisplayPort, OPS/PC, Android, VGA |
| Volume | Number | 0–100 |
| Brightness, Contrast | Number | Only accepted on external inputs (HDMI/DP/PC), not on the Android home screen |
| Key up/down/left/right/OK/input/menu/exit | Buttons | Same as the board's front keys |
| Button lock | Switch | Locks front panel and remote, except power |
| Power button lock | Switch | Locks the power key |
| Menu lock | Switch | The board can't report this one, so Home Assistant shows the last state it set |
| Current input | Sensor | |
| Input signal | Binary sensor | On when the current input has a signal |
| Internal temperature | Sensor | Diagnostic |
| Operating hours | Sensor | Diagnostic |
| Network control | Binary sensor | Off when the board isn't answering on port 5000 |
| IP address | Sensor | Diagnostic; updates when the board is found at a new address |
| Search network for board | Button | Diagnostic; searches for the board's MAC right away |

The board is polled every 10 seconds.

## Turning boards on

When a board is in standby it may stop answering on the network, depending on its power-saving
settings. The Power switch and the media player's turn-on send a Wake-on-LAN packet first, then
the power-on command. If boards don't wake, look in the board's settings for a network standby or
Wake-on-LAN option. Home Assistant must be on the same network segment for Wake-on-LAN to reach it.

## Opening apps

The control port can't launch apps. For that, turn on network ADB on the board and add it with
Home Assistant's built-in **Android Debug Bridge** integration (`androidtv`), which can launch apps
and send Android commands. The two integrations can be used side by side.
