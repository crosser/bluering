from asyncio import Event
from datetime import datetime, timezone
from struct import pack, unpack
from typing import Any, Dict

verbose: bool = False


def opsv2_verbosity(verbosity: bool) -> None:
    global verbose
    verbose = verbosity


class Opv2:
    OPCODE: int
    kwargs: Dict[str, Any]
    data: bytes
    sndbuf: bytes = b""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.done = Event()
        self.data = b""
        self.expect = 0

    def send(self) -> bytes:
        data = b"\xbc" + pack("B", self.OPCODE) + self.sndbuf
        return data + pack("B", sum(data) % 256)

    def recv(self, char, data: bytes) -> None:
        if verbose:
            print(self.__class__.__name__, "received:", data.hex())
        if not self.data:  # First frame
            if data[0] != b"\xbc":
                print("Unexpeted frame tag", data.hex())
                return
            self.expect = (data[3] << 8) | data[2]
            if verbose:
                print("Expect packet size", self.expect)
        self.data = self.data + data
        if len(self.data) >= self.expect + 6:
            self.done.set()

    def result(self) -> str:
        return data.hex()


class SPO2Log(Opv2):
    """
    Report history of SpO2 measurements.
    """

    OPCODE = 0x2A

    sndbuf = b"\x01\x00\xff\x00\xff"
