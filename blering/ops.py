from asyncio import Event
from datetime import datetime, timezone
from struct import pack, unpack
from typing import Any, Dict, List, NamedTuple


class StepInfo(NamedTuple):
    date: str
    time_index: int
    calories: int
    steps: int
    distance: int


class Op:
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
        print("received:", data)
        if len(data) != 16:
            print("Response", data.hex(), "has wrong length", len(data))
        if data[0] != self.OPCODE:
            print("Response", data.hex(), "opcode mismatch", self.OPCODE)
        if sum(data[:-1]) % 256 != data[-1]:
            print("Response", data.hex(), "checksum mismatch")
        self.data.append(data)
        if not self.MULTI:
            self.done.set()

    def result(self) -> str:
        return "\n".join([el.hex() for el in self.data])


class Battery(Op):
    OPCODE = 0x03

    def result(self) -> str:
        return f"{self.data[0][1]}%"


class Blink(Op):
    OPCODE = 0x10

    def result(self) -> str:
        return "Hopefully, the ring just blinked twice"


class ReadSteps(Op):
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
            ti, cal, st, di = unpack("<BHHH", fr[4:11])
            y += 2000
            if new_cal_proto:
                cal *= 10
            steps.append(
                StepInfo(datetime(y, m, d).isoformat(), ti, cal, st, di)
            )
        return "\n".join(str(el) for el in steps)


class SetTime(Op):
    OPCODE = 0x01

    @property
    def sndbuf(self) -> bytes:
        # opcode + 6 bytes of datatime in BCD + 1 for English language(?)
        return (
            bytes.fromhex(
                "".join(
                    f"{(el % 100):02d}"
                    for el in datetime.now()
                    .astimezone(tz=timezone.utc)
                    .timetuple()[:6]
                )
            )
            + b"\1"
        )


class HRLog(Op):
    OPCODE = 0x15
    MULTI = True

    @property
    def sndbuf(self) -> bytes:
        # opcode + timestamp of past midnight
        return pack(
            "<L",
            round(
                datetime.fromisoformat(
                    datetime.now()
                    .astimezone(tz=timezone.utc)
                    .strftime("%Y-%m-%d")
                ).timestamp()
            ),
        )

    def recv(self, char, data: bytes) -> None:
        if not self.data:  # First frame
            self.frames = data[2]
            print("expect", self.frames, "frames")
            self.count = 0
        if data[1] != self.count:
            print("count mismatch", data.hex(), "expected", self.count)
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
        prelude = bulk[:17]
        (ts,) = unpack("<L", bulk[13:17])
        print("time:", datetime.fromtimestamp(ts).isoformat())
        log = (
            f"{datetime.fromtimestamp(ts + (i * 300)).isoformat()}: {v}"
            for i, v in enumerate(bulk[17:])
            if v
        )
        return "\n".join(str(el) for el in log)
        # log = [bulk[i : i + 12] for i in range(0, len(bulk), 12)]
        # return "\n".join(bytes(el).hex() for el in log)


class LogSettings(Op):
    OPCODE = 0x16

    @property
    def sndbuf(self) -> bytes:
        if self.kwargs:
            opmode = b"\x02"
            enabled = (
                b"\x01"
                if self.kwargs.get("enabled", "yes") == "yes"
                else b"\x02"
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
