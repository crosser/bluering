from asyncio import Event
from datetime import datetime, timezone
from struct import pack
from typing import Any, Dict, List


class Op:
    OPCODE: int
    MULTI: bool = False
    kwargs: Dict[str, Any]
    data: List[bytes]

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.done = Event()
        self.data = []

    @property
    def sndbuf(self) -> bytes:
        return chr(self.OPCODE).encode()

    def send(self) -> bytes:
        return (
            self.sndbuf.ljust(15, b"\0") + chr(sum(self.sndbuf) % 256).encode()
        )

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
        return [el.hex() for el in self.data]


class Battery(Op):
    OPCODE = 0x03

    def result(self) -> str:
        return f"{self.data[0][1]}%"


class Blink(Op):
    OPCODE = 0x10

    def result(self) -> str:
        return "Hopefully, the ring blinked twice"


class SetTime(Op):
    OPCODE = 0x01

    @property
    def sndbuf(self) -> bytes:
        # opcode + 6 bytes of datatime in BCD + 1 for English language(?)
        return (
            super().sndbuf
            + bytes.fromhex(
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
        return super().sndbuf + pack(
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
        log = [bulk[i:i+12] for i in range(0, len(bulk), 12)]
        return "\n".join(bytes(el).hex() for el in log)


#        #send = b"\x16\x01" # read settings
#        #send = b"\x16\x02\x01\x1e"  # write settings, enabled, 30 min
#        #send = b"\x43"  # read "sports data"
