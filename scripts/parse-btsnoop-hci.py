#!/usr/bin/python3

# Needs `tshark` installed somewhere in the $PATH

from sys import argv
from json import load
from subprocess import Popen, PIPE

proc = Popen(["tshark", "-r", argv[1], "-Y", "_ws.col.protocol==ATT", "-x", "-T", "json"], stdout=PIPE)
obj = load(proc.stdout)
rc = proc.wait()
for el in obj:
    btatt = el.get("_source", {}).get("layers", {}).get("btatt", {})
    rx = btatt.get("btgatt.nordic.uart_rx_raw", [None])[0]
    tx = btatt.get("btgatt.nordic.uart_tx_raw", [None])[0]
    if rx is not None:
        print("<", rx)
    elif tx is not None:
        print(">", tx)
