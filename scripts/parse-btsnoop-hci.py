#!/usr/bin/python3

# Needs `tshark` installed somewhere in the $PATH

from sys import argv
from json import load
from subprocess import Popen, PIPE

if len(argv) > 2:
    yfilter = f'(_ws.col.protocol==ATT) && (frame.time>="{argv[2]}")'
else:
    yfilter = "_ws.col.protocol==ATT"

proc = Popen(["tshark", "-r", argv[1], "-Y", yfilter, "-x", "-T", "json"],
             stdout=PIPE)
obj = load(proc.stdout)
rc = proc.wait()
for el in obj:
    btatt = el.get("_source", {}).get("layers", {}).get("btatt", {})
    rx = btatt.get("btgatt.nordic.uart_rx_raw", [None])[0]
    tx = btatt.get("btgatt.nordic.uart_tx_raw", [None])[0]
    command = btatt.get("btatt.opcode", None)
    value = btatt.get("btatt.value_raw", [None])[0]
    if rx is not None:
        print("1<", rx)
    elif tx is not None:
        print("1>", tx)
    elif value is not None:
        print("2>" if command == "0x52" else "2<", value)

# Packet V2 format:
# 1 byte SYN - constant 0xbc
# 1 byte OPCODE
# 2 bytes payload length, little endian
# variable length payload, may span multiple BT frames
# 2 bytes CRC
