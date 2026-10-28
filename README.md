# ViewSonic ViewBoard for Home Assistant

Control ViewSonic ViewBoard interactive displays (tested on an IFP7550-3) over the network,
using the board's built-in LAN control port (TCP 5000). Each board is added by IP address
and shows up as its own device.

## Install

**Manually:** copy the `custom_components/viewsonic_viewboard` folder into your Home Assistant
`config/custom_components/` folder (create it if it doesn't exist), then restart Home Assistant.

**With HACS:** put this folder in a Git repository, then in HACS choose
*⋮ → Custom repositories*, paste the repository URL, pick type *Integration*, and install.
Restart Home Assistant.

## Add a board

*Settings → Devices & services → Add integration → ViewSonic ViewBoard*, then enter the IP
address and, optionally, a name such as "Room 112". Repeat for each board.

If a board's IP address changes: open the board's entry, choose *⋮ → Reconfigure*, and enter the
new address. The board is recognized by its serial number, so its entities and automations keep working.

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
