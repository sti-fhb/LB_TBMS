"""
GoDEX EZIO DLL 封裝 + EZPL 指令產生器。

USB 模式：透過 EZio64/32.dll 直接呼叫 DLL 函式（ecTextOut / Bar / sendcommand）
TCP/FILE 模式：產生 raw EZPL 指令字串
"""

from __future__ import annotations
import ctypes
import os
import socket
import struct
from enum import Enum


# ═══════════════════════════════════════════════════════════════
#  LinkType
# ═══════════════════════════════════════════════════════════════

class LinkType(Enum):
    USB = "USB"       # 實體 USB 線路
    TCP = "TCP"       # 固定 IP（LAN）
    BT = "BT"         # 藍牙（OS 層命名）
    FILE = "FILE"     # 檔案輸出（測試用）


# ═══════════════════════════════════════════════════════════════
#  GodexPrinter — DLL 封裝（USB 模式直接呼叫 DLL 函式）
# ═══════════════════════════════════════════════════════════════

class GodexPrinter:
    """
    GoDEX 印表機控制。

    USB 模式下直接呼叫 DLL 函式：
      - setup()       → DLL setup()
      - sendcommand() → DLL sendcommand()
      - ecTextOut()   → DLL ecTextOut()    ← 文字輸出（TrueType）
      - bar()         → DLL Bar()          ← 條碼輸出
      - job_start()   → sendcommand("^L")
      - job_end()     → sendcommand("E")

    TCP 模式下產生 raw EZPL 指令送出。
    FILE 模式下產生 raw EZPL 指令存檔。
    """

    def __init__(self, link_type: LinkType = LinkType.USB) -> None:
        self.link_type = link_type
        self._dll: ctypes.WinDLL | None = None
        self._sock: socket.socket | None = None
        self._connected = False
        self._file_commands: list[str] = []

    # ── Connection ───────────────────────────────────────────────

    def open(self, ip: str = "", tcp_port: int = 9100,
             usb_port: str = "6", bt_name: str = "") -> None:
        """
        開啟印表機連線。

        Args:
            ip: 印表機 IP（TCP 模式）
            tcp_port: 印表機 Port（TCP 模式，預設 9100）
            usb_port: USB Port ID（USB 模式，預設 "6"）
            bt_name: 藍牙印表機名稱（BT 模式，OS 層命名）
        """
        if self._connected:
            self.close()

        if self.link_type == LinkType.USB:
            self._dll = self._load_dll()
            ret = self._dll.openport(usb_port.encode("ascii"))
            if ret != 1:
                raise ConnectionError(f"USB 開啟失敗 (openport('{usb_port}') 回傳 {ret})")
            self._connected = True

        elif self.link_type == LinkType.TCP:
            # DLL OpenNet 或直接 socket
            self._dll = self._load_dll()
            ret = self._dll.OpenNet(
                ip.encode("ascii"),
                str(tcp_port).encode("ascii"),
            )
            if ret != 1:
                # fallback: 直接 socket
                self._dll = None
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(5)
                self._sock.connect((ip, tcp_port))
            self._connected = True

        elif self.link_type == LinkType.BT:
            # 藍牙：透過 DLL OpenDriver，以 OS 印表機名稱連線
            if not bt_name:
                raise ConnectionError("藍牙模式需指定印表機名稱（bt_name）")
            self._dll = self._load_dll()
            ret = self._dll.OpenDriver(bt_name.encode("big5", errors="replace"))
            if ret != 1:
                raise ConnectionError(
                    f"藍牙開啟失敗 (OpenDriver('{bt_name}') 回傳 {ret})")
            self._connected = True

        elif self.link_type == LinkType.FILE:
            self._file_commands = []
            self._connected = True

    def close(self) -> None:
        if self.link_type in (LinkType.USB, LinkType.TCP, LinkType.BT) and self._dll:
            self._dll.closeport()
            self._dll = None
        elif self.link_type == LinkType.TCP and self._sock:
            self._sock.close()
            self._sock = None
        self._connected = False

    # ── Label Setup ──────────────────────────────────────────────

    def label_setup(
        self,
        width: int = 80,
        height: int = 85,
        gap: int = 3,
        darkness: int = 12,
        speed: int = 2,
    ) -> None:
        """對應 VB6 LabelSetup()。"""
        if self._dll:
            # DLL setup(mm, dark, speed, mode, gap, top)
            #   mode: 0=gap, 1=continuous
            self._dll.setup(height, darkness, speed, 0, gap, 0)
            self._dll.sendcommand(f"^W{width}".encode())
        else:
            self._raw_cmd(f"^Q{height},{gap}")
            self._raw_cmd("~S,OFFSETX,0")
            self._raw_cmd("^R0")
            self._raw_cmd(f"^W{width}")
            self._raw_cmd(f"^H{darkness}")
            self._raw_cmd(f"^S{speed}")
            self._raw_cmd("^P1")
            self._raw_cmd("^C1")

    # ── Job Control ──────────────────────────────────────────────

    def job_start(self) -> None:
        """對應 VB6 JobStart() → sendcommand("^L")"""
        self._send_cmd("^L")

    def job_end(self) -> None:
        """對應 VB6 JobEnd() → sendcommand("E")"""
        self._send_cmd("E")

    # ── Text Output ──────────────────────────────────────────────

    def text_out(
        self,
        x: int,
        y: int,
        height: int,
        font_name: str,
        text: str,
    ) -> None:
        """
        對應 VB6 ecTextOut(x, y, height, fontName, text)。

        USB: 呼叫 DLL ecTextOut（使用 TrueType 字型）
        TCP/FILE: 產生 EZPL A-command（內建字型近似）
        """
        if self._dll:
            self._dll.ecTextOut(
                x, y, height,
                font_name.encode("big5", errors="replace"),
                text.encode("big5", errors="replace"),
            )
        else:
            fid = self._map_font(height)
            self._raw_cmd(f'A{x},{y},0,{fid},1,1,N,"{text}"')

    def text_out_bold(
        self,
        x: int,
        y: int,
        height: int,
        font_name: str,
        text: str,
    ) -> None:
        """粗體 — 偏移 1dot 疊印。"""
        self.text_out(x, y, height, font_name, text)
        self.text_out(x + 1, y, height, font_name, text)

    # ── Barcode Output ───────────────────────────────────────────

    def barcode(
        self,
        barcode_type: str,
        x: int,
        y: int,
        narrow: int,
        wide: int,
        height: int,
        rotation: int = 0,
        readable: int = 1,
        data: str = "",
    ) -> None:
        """
        對應 VB6 BAR_Verify() → Bar()。

        USB: 呼叫 DLL Bar(type, x, y, narrow, wide, height, rotation, readable, data)
        TCP/FILE: 產生 EZPL B-command
        """
        if self._dll:
            self._dll.Bar(
                barcode_type.encode("ascii"),
                x, y, narrow, wide, height, rotation, readable,
                data.encode("ascii", errors="replace"),
            )
        else:
            rot = {0: 0, 90: 1, 180: 2, 270: 3}.get(rotation, 0)
            self._raw_cmd(
                f'B{x},{y},{rot},{barcode_type},{narrow},{wide},{height},{readable},"{data}"'
            )

    # ── Rotated / Fine Text ─────────────────────────────────────

    def text_out_r(
        self,
        x: int, y: int, height: int,
        font_name: str, text: str,
        width: int = 0, weight: int = 0, degree: int = 0,
    ) -> None:
        """對應 VB6 ecTextOutR(x, y, height, fontName, text, width, weight, degree)。"""
        if self._dll:
            self._dll.ecTextOutR(
                x, y, height,
                font_name.encode("big5", errors="replace"),
                text.encode("big5", errors="replace"),
                width, weight, degree,
            )
        else:
            rot = {0: 0, 90: 1, 180: 2, 270: 3}.get(degree, 0)
            fid = self._map_font(height)
            self._raw_cmd(f'A{x},{y},{rot},{fid},1,1,N,"{text}"')

    def text_out_fine(
        self,
        x: int, y: int, height: int,
        font_name: str, text: str,
        width: int = 0, weight: int = 0, degree: int = 0,
        italic: int = 0, underline: int = 0, strikeout: int = 0,
        inverse: int = 0,
    ) -> None:
        """對應 VB6 ecTextOutFine(x,y,h,font,text,w,weight,deg,i,u,s,inv)。"""
        if self._dll:
            self._dll.ecTextOutFine(
                x, y, height,
                font_name.encode("big5", errors="replace"),
                text.encode("big5", errors="replace"),
                width, weight, degree, italic, underline, strikeout, inverse,
            )
        else:
            rot = {0: 0, 90: 1, 180: 2, 270: 3}.get(degree, 0)
            fid = self._map_font(height)
            nr = "R" if inverse else "N"
            self._raw_cmd(f'A{x},{y},{rot},{fid},1,1,{nr},"{text}"')

    # ── Image ────────────────────────────────────────────────────

    def put_image(
        self, x: int, y: int, filename: str, degree: int = 0,
    ) -> None:
        """對應 VB6 putimage(x, y, filename, degree)。"""
        if self._dll:
            self._dll.putimage(
                x, y,
                filename.encode("ascii", errors="replace"),
                degree,
            )
        else:
            # FILE/TCP 模式無法嵌入圖片，輸出註解
            self._raw_cmd(f'; IMAGE {filename} at ({x},{y})')

    # ── Drawing ──────────────────────────────────────────────────

    def draw_hor_line(self, x: int, y: int, length: int, thickness: int = 2) -> None:
        """對應 VB6 DrawHorLine(x, y, length, thickness)。"""
        if self._dll:
            self._dll.DrawHorLine(x, y, length, thickness)
        else:
            self._raw_cmd(f"LO{x},{y},{length},{thickness}")

    def draw_ver_line(self, x: int, y: int, length: int, thickness: int = 2) -> None:
        """對應 VB6 DrawVerLine(x, y, length, thickness)。"""
        if self._dll:
            self._dll.DrawVerLine(x, y, length, thickness)
        else:
            self._raw_cmd(f"LO{x},{y},{thickness},{length}")

    def draw_rec(self, x: int, y: int, w: int, h: int, lrw: int = 2, ubw: int = 2) -> None:
        """對應 VB6 DrawRec(x, y, w, h, lrw, ubw)。"""
        if self._dll:
            self._dll.DrawRec(x, y, w, h, lrw, ubw)
        else:
            # 用 4 條線模擬矩形
            self._raw_cmd(f"LO{x},{y},{w},{ubw}")
            self._raw_cmd(f"LO{x},{y+h},{w},{ubw}")
            self._raw_cmd(f"LO{x},{y},{lrw},{h}")
            self._raw_cmd(f"LO{x+w},{y},{lrw},{h}")

    # ── File Output ──────────────────────────────────────────────

    def get_commands(self) -> str:
        """取得 FILE 模式累積的 EZPL 指令。"""
        return "\r\n".join(self._file_commands) + "\r\n"

    def save(self, path: str) -> None:
        """存檔（FILE 模式）。"""
        with open(path, "w", encoding="ascii", errors="replace") as f:
            f.write(self.get_commands())

    # ── Internal ─────────────────────────────────────────────────

    def _send_cmd(self, cmd: str) -> None:
        """送出控制指令（^L / E 等）。"""
        if self._dll:
            self._dll.sendcommand(cmd.encode("ascii"))
        else:
            self._raw_cmd(cmd)

    def _raw_cmd(self, cmd: str) -> None:
        """TCP 送出 / FILE 累積。"""
        if self.link_type == LinkType.TCP and self._sock:
            self._sock.sendall((cmd + "\r\n").encode("ascii", errors="replace"))
        elif self.link_type == LinkType.FILE:
            self._file_commands.append(cmd)

    @staticmethod
    def _load_dll() -> ctypes.WinDLL:
        dll_name = "EZio64.dll" if struct.calcsize("P") * 8 == 64 else "Ezio32.dll"
        search_paths = [
            os.path.join(r"C:\ezio", dll_name),
            os.path.join(os.path.dirname(__file__), dll_name),
        ]
        for p in search_paths:
            if os.path.exists(p):
                return ctypes.WinDLL(p)
        raise FileNotFoundError(
            f"找不到 {dll_name}。搜尋路徑: {search_paths}"
        )

    @staticmethod
    def _map_font(size: int) -> int:
        if size <= 38:
            return 3
        if size <= 60:
            return 4
        return 5

    # ── Context Manager ──────────────────────────────────────────

    def __enter__(self) -> GodexPrinter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def connected(self) -> bool:
        return self._connected
