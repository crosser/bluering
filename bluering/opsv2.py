from asyncio import Event
from datetime import datetime, timezone, timedelta, date
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
            if len(data) < 6:
                print("Too short data", data.hex())
                return
            if data[0] != 0xBC:
                print("Unexpected frame tag", data.hex())
                return
            if data[1] != self.OPCODE:
                print("Opcode mismatch", data.hex())
            self.expect = (data[3] << 8) | data[2]
            if verbose:
                print("Expect packet size", self.expect)
        self.data = self.data + data
        if len(self.data) >= self.expect + 6:
            self.payload = memoryview(self.data)[6 : 6 + self.expect]
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
        days, rest = divmod(len(self.payload), 49)
        if rest:
            print("payload is not a round number of days", self.payload.hex())
        dgrps = (self.payload[i * 49 : (i + 1) * 49] for i in range(days))
        recs = (
            (day[0], hr, lo, hi)
            for day in dgrps
            for hr, (lo, hi) in enumerate(
                (day[1:][i * 2], day[1:][i * 2 + 1]) for i in range(24)
            )
            if day
        )
        dated_recs = (
            (
                datetime(
                    *(
                        (date.today() - timedelta(days=ddif)).timetuple()[:3]
                        + (hr,)
                    )
                ),
                lo,
                hi,
            )
            for ddif, hr, lo, hi in recs
        )
        return "\n".join(
            f"{dt.isoformat()}: {lo} - {hi}"
            for dt, lo, hi in dated_recs
            if lo or hi
        )
