from asyncio import Event
from datetime import datetime, timezone
from struct import pack, unpack
from typing import Any, Dict

verbose: bool = False


def opsv2_verbosity(verbosity: bool) -> None:
    global verbose
    verbose = verbosity


class Opv2:
    UART_SRV_UUID = "de5bf728-d711-4e47-af26-65e3012a5dc7"
    UART_WRT_UUID = "de5bf72a-d711-4e47-af26-65e3012a5dc7"
    UART_NOT_UUID = "de5bf729-d711-4e47-af26-65e3012a5dc7"
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
            if data[0] != 0xBC:
                print("Unexpeted frame tag", data.hex())
                return
            self.expect = (data[3] << 8) | data[2]
            if verbose:
                print("Expect packet size", self.expect)
        self.data = self.data + data
        if len(self.data) >= self.expect + 6:
            self.done.set()

    def result(self) -> str:
        return self.data.hex()


class SPO2Log(Opv2):
    """
    Report history of SpO2 measurements.
    """

    OPCODE = 0x2A

    sndbuf = b"\x01\x00\xff\x00\xff"

    def result(self) -> str:
        days = (
            memoryview(self.data)[6 : 6 + self.expect][i * 49 : (i + 1) * 49]
            for i in range(7)
        )
        return "\n".join(
            "\n".join(
                f"{day[0]}: {day[1:][i*2]}-{day[1:][i*2+1]}" for i in range(24)
            )
            for day in days
            if day
        )
