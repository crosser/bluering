#!/usr/bin/python3

import asyncio
from getopt import getopt
from inspect import isclass
from sys import argv
from typing import Optional, Union

from bleak import BleakScanner, BleakClient

from .opsv1 import *
from .opsv2 import *

OPS = {
    cls.__name__.lower(): cls
    for name, cls in globals().items()
    if isclass(cls)
    and (issubclass(cls, Opv1) or issubclass(cls, Opv2))
    and cls is not Opv1
    and cls is not Opv2
}

Op = Union[Opv1, Opv2]

verbose = False

# This is a "fake" service: the device does not support it, and it does
# not show up after connect and service discovery. But it is included in
# the advertisements, so we will use it to detect the peripheral that we
# want.
ADV_SRV_UUID = "00003802-0000-1000-8000-00805f9b34fb"
# DEV_INFO_UUID = "0000180a-0000-1000-8000-00805f9b34fb"


def show(bstr):
    try:
        return bstr.decode("ascii")
    except UnicodeDecodeError:
        return bstr.hex()


async def main(addr: Optional[str], op: Op):
    fdev = None
    async with BleakScanner() as scanner:
        async for dev, data in scanner.advertisement_data():
            print(
                "address",
                dev.address,
                "name",
                dev.name,
                "rssi",
                data.rssi,
                end="\033[K\r",
            )
            if (
                (addr is not None and dev.address == addr)
                or data.service_uuids
                and ADV_SRV_UUID in data.service_uuids
            ):
                fdev = dev
                print("Found", fdev, end="\033[K\n")
                break
    async with BleakClient(fdev) as client:
        srvd = {srv.uuid: srv for srv in client.services}
        if verbose:
            print("Services:")
            for k, s in srvd.items():
                print(k)
                for char in s.characteristics:
                    print(f"\t{char.uuid}: {char.description}: ")
                    print(f"\t{char.properties}: ")
                    if "read" in char.properties:
                        print(
                            f"\t\tValue: {show(await client.read_gatt_char(char))}"
                        )
                    if "write-without-response" in char.properties:
                        print(
                            f"\t\tWWR max size {char.max_write_without_response_size}"
                        )
        if op.UART_SRV_UUID not in srvd:
            print("Service", op.UART_SRV_UUID, "not found")
            return
        if {op.UART_WRT_UUID, op.UART_NOT_UUID} != {
            c.uuid for c in srvd[op.UART_SRV_UUID].characteristics
        }:
            print("Characteristics not found")
            return
        await client.start_notify(op.UART_NOT_UUID, op.recv)
        await client.write_gatt_char(
            op.UART_WRT_UUID, op.send(), response=False
        )
        await op.done.wait()
        await client.disconnect()
    print(op.result())


async def shutdown():
    print("Shutdown complete")


if __name__ == "__main__":
    topts, args = getopt(argv[1:], "hva:")
    opts = dict(topts)
    verbose = "-v" in opts
    opsv1_verbosity(verbose)
    opsv2_verbosity(verbose)
    if len(args) == 0 or "-h" in opts or args[0] not in OPS:
        print(f"Usage: {argv[0]} [-h] [-v] [-a ADDR] command [key=value ...]")
        if len(args) > 0 and args[0] in OPS:
            print("Command", args[0], ":", OPS[args[0]].__doc__)
        else:
            print("Commands are:", ", ".join(OPS.keys()))
        exit(0)
    kwargs = dict(el.split(sep="=", maxsplit=1) for el in args[1:])
    op = OPS[args[0]](**kwargs)
    try:
        asyncio.run(main(opts.get("a", None), op))
    except KeyboardInterrupt:
        asyncio.run(shutdown())
