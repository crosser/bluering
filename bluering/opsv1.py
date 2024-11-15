from asyncio import Event
from datetime import datetime, timezone
from struct import pack, unpack
from typing import Any, Dict, List, NamedTuple

verbose: bool = False


def opsv1_verbosity(verbosity: bool) -> None:
    global verbose
    verbose = verbosity


class StepInfo(NamedTuple):
    date: str
    calories: int
    steps: int
    distance: int


class Opv1:
    UART_SRV_UUID = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
    UART_WRT_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    UART_NOT_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    OPCODE: int
    MULTI: bool = False
    kwargs: Dict[str, Any]
    data: List[bytes]
    sndbuf: bytes = b""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.done = Event()
        self.data = []

    def send(self) -> bytes:
        data = pack("B", self.OPCODE) + self.sndbuf.ljust(14, b"\0")
        return data + pack("B", sum(data) % 256)

    def recv(self, char, data: bytes) -> None:
        # print("char", char)
        if verbose:
            print(self.__class__.__name__, "received:", data.hex())
        if len(data) != 16:
            print("Response", data.hex(), "has wrong length", len(data))
        if (data[0] & 0x7F) != self.OPCODE:
            print("Response", data.hex(), "opcode mismatch", self.OPCODE)
        if sum(data[:-1]) % 256 != data[-1]:
            print("Response", data.hex(), "checksum mismatch")
        self.data.append(data)
        if not self.MULTI:
            self.done.set()

    def result(self) -> str:
        return "\n".join([el.hex() for el in self.data])


class Battery(Opv1):
    """
    Report battery charge percentage
    """

    OPCODE = 0x03

    def result(self) -> str:
        return f"{self.data[0][1]}%{', charging' if self.data[0][2] else ''}"


class Blink(Opv1):
    """
    Blink twice
    """

    OPCODE = 0x10

    def result(self) -> str:
        return "Hopefully, the ring just blinked twice"


class ActLog(Opv1):
    """
    Report history of step count and other health data
    """

    OPCODE = 0x43
    NULTI = True
    sndbuf = b"\x00\x0f\x00\x5f\x01"

    def recv(self, char, data: bytes) -> None:
        if not self.data:  # First frame
            if data[1] != 0xF0:
                print("Received", data.hex(), "bad first frame")
            self.frames = data[2]
            # print("expect", self.frames, "more frames")
            self.count = 0
        else:
            if data[5] != self.count - 1:
                print("Received", data.hex(), "byte 5 must be", self.count - 1)
            if data[6] != self.frames:
                print("Received", data.hex(), "byte 6 must be", self.frames)
        super().recv(char, data)
        self.count += 1
        if self.count > self.frames:
            # print("report done receiving")
            self.done.set()

    def result(self) -> str:
        new_cal_proto = self.data[0][3] == 1
        steps = []
        for fr in self.data[1:]:
            y, m, d = (
                int(el.decode())
                for el in unpack("2s2s2s", fr[1:4].hex().encode())
            )
            # fr[4] is the number of quarter-an-hours from midnight
            hr = fr[4] // 4
            mi = (fr[4] % 4) * 15
            cal, st, di = unpack("<HHH", fr[7:13])
            y += 2000
            if new_cal_proto:
                cal *= 10
            steps.append(
                StepInfo(datetime(y, m, d, hr, mi).isoformat(), cal, st, di)
            )
        return "\n".join(str(el) for el in steps)


class SetTime(Opv1):
    """
    Synchronize clock in the ring with the computer
    """

    OPCODE = 0x01
    MULTI = True

    @property
    def sndbuf(self) -> bytes:
        # opcode + 6 bytes of datatime in BCD + 1 for English language(?)
        # Note that this datetime representation depends on the timezone,
        # i.e. if converted to time_t, it will _not_ be true time.
        # Official Android app sends representaton for the local time zone:
        # Oct 22, 2024 23:18:56.224381000 CEST
        #     01241022 23 18 56 0100000000000000e9
        TZ = None  # or set TZ = timezone.utc for UTC
        return (
            bytes.fromhex(
                "".join(
                    f"{(el % 100):02d}"
                    for el in datetime.now().astimezone(tz=TZ).timetuple()[:6]
                )
            )
            + b"\1"
        )

    def recv(self, char, data: bytes) -> None:
        super().recv(char, data)
        if (data[0] & 0x7F) == self.OPCODE:
            self.done.set()


class HRLog(Opv1):
    """
    Report one day worth of HR measurements.
    Optionally specify the date of interest in the form "date=YYYY-MM-DD".
    Default is the current day.
    """

    OPCODE = 0x15
    MULTI = True

    @property
    def sndbuf(self) -> bytes:
        # opcode + timestamp of past midnight
        if self.kwargs:
            ref = datetime.fromisoformat(self.kwargs.get("date"))
        else:
            ref = datetime.now()
        print("Time ref", ref)
        TZ = None  # TZ = timezone.utc
        return pack(
            "<L",
            86400
            + round(datetime(*ref.timetuple()[:3], tzinfo=TZ).timestamp()),
        )

    def recv(self, char, data: bytes) -> None:
        if not self.data:  # First frame
            self.frames = data[2]
            # print("expect", self.frames, "frames")
            self.count = 0
        if data[1] != self.count:
            if data[1] == 0xFF:  # No data
                self.done.set()
                return
            else:
                print(
                    "count mismatch",
                    data.hex(),
                    "expected",
                    self.count,
                    "of",
                    self.frames,
                )
        self.count += 1
        super().recv(char, data)
        # print("got", self.count, "of", self.frames)
        if self.count >= self.frames:
            # print("report done receiving")
            self.done.set()

    def result(self) -> str:
        # We have N frames with 13 bytes of payload in each, and that is
        # a concatanation of 12 byte structures
        bulk = memoryview(b"".join(buf[2:-1] for buf in self.data))
        if len(bulk) < 17:
            return "No HR log data"
        (ts,) = unpack("<L", bulk[13:17])
        TZ = None  # TZ = timezone.utc
        log = (
            f"{datetime.fromtimestamp(ts - 86400 + (i * 300))
                .astimezone(tz=TZ).isoformat()}: {v}"
            for i, v in enumerate(bulk[17:])
            if v
        )
        return "\n".join(str(el) for el in log)


class HRPref(Opv1):
    """
    Report or change HR log preferences.
    To set new period in minutes, specify "period=NN"
    """

    OPCODE = 0x16

    @property
    def sndbuf(self) -> bytes:
        if self.kwargs:
            opmode = b"\x02"
            enabled = (
                b"\x01"
                if self.kwargs.get("enabled", "yes") == "yes"
                else b"\x00"
            )
            period = pack("B", int(self.kwargs.get("period", "60")))
            return opmode + enabled + period
        else:
            return b"\x01"

    def result(self) -> str:
        if self.kwargs:
            return "Done, hopefully"
        return (
            f"{'enabled' if self.data[0][2] == 1 else 'disabled'},"
            f" period {self.data[0][3]} min"
        )


class SpO2Pref(Opv1):
    """
    Report or change SpO2 log enabled/disabled status.
    To change, specify "enabled={yes/no}"
    """

    OPCODE = 0x2C

    @property
    def sndbuf(self) -> bytes:
        if self.kwargs:
            opmode = b"\x02"
            enabled = (
                b"\x01"
                if self.kwargs.get("enabled", "yes") == "yes"
                else b"\x02"
            )
            return opmode + enabled
        else:
            return b"\x01"

    def result(self) -> str:
        if self.kwargs:
            return "Done, hopefully"
        return f"{'enabled' if self.data[0][2] == 1 else 'disabled'},"
