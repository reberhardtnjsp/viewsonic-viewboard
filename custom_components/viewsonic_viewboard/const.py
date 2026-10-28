"""Constants for the ViewSonic ViewBoard integration."""

from datetime import timedelta

DOMAIN = "viewsonic_viewboard"

DEFAULT_PORT = 5000
SCAN_INTERVAL = timedelta(seconds=10)

CONF_MAC = "mac"
CONF_ARP_MAC = "arp_mac"

# Input source codes (Set ", Get j) -> friendly names
INPUT_SOURCES = {
    "004": "HDMI 1",
    "014": "HDMI 2",
    "024": "HDMI 3",
    "034": "HDMI 4",
    "009": "DisplayPort",
    "007": "OPS / Slot-in PC",
    "00A": "Android",
    "006": "VGA",
}
SOURCE_CODES = {name: code for code, name in INPUT_SOURCES.items()}

# Keypad key simulation (Set A)
KEYPAD_KEYS = {
    "up": "000",
    "down": "001",
    "left": "002",
    "right": "003",
    "enter": "004",
    "input": "005",
    "menu": "006",
    "exit": "007",
}
