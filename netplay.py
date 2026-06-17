"""Tiny LAN networking for Chess-cards.

Transport only: UDP beacon so a client can find the host without typing an IP,
plus a TCP link that ships length-prefixed binary frames. The game decides what
to put in those frames (it pickles GameState.__dict__).

Design: turn-based and host-authoritative, so this stays deliberately small -
one socket each way, a background receive thread, and a thread-safe inbox the
main (pygame) loop drains each frame.
"""

import socket
import struct
import threading
import queue
import time

DISCOVERY_PORT = 50777      # UDP: host beacon
GAME_PORT = 50778           # TCP: game data
MAGIC = b"CHESSCARDS1:"     # discovery beacon tag, followed by the host IP


def local_ip():
    # Best-effort LAN IP (no packets are actually sent by connect() on UDP).
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class NetLink:
    def __init__(self):
        self.role = None            # "host" | "client"
        self.connected = False
        self.error = None
        self.local_ip = local_ip()
        self.inbox = queue.Queue()
        self._sock = None
        self._stop = threading.Event()
        self._beacon_stop = threading.Event()

    # ---------------------------------------------------------------- hosting
    def host(self):
        self.role = "host"
        threading.Thread(target=self._host_thread, daemon=True).start()
        threading.Thread(target=self._beacon_thread, daemon=True).start()

    def _beacon_thread(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        msg = MAGIC + self.local_ip.encode()
        while not self._beacon_stop.is_set() and not self.connected:
            try:
                udp.sendto(msg, ("255.255.255.255", DISCOVERY_PORT))
            except Exception:
                pass
            time.sleep(0.5)
        udp.close()

    def _host_thread(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", GAME_PORT))
            srv.listen(1)
            srv.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    conn, _addr = srv.accept()
                except socket.timeout:
                    continue
                self._sock = conn
                self._beacon_stop.set()
                self.connected = True
                break
            srv.close()
            if self._sock is not None:
                self._recv_loop()
        except Exception as exc:
            self.error = str(exc)

    # ---------------------------------------------------------------- joining
    def join(self, host_ip=None):
        self.role = "client"
        threading.Thread(target=self._join_thread, args=(host_ip,), daemon=True).start()

    def _discover(self, timeout=8.0):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            udp.bind(("", DISCOVERY_PORT))
        except Exception as exc:
            self.error = "discovery bind failed: %s" % exc
            udp.close()
            return None
        udp.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop.is_set():
            try:
                data, addr = udp.recvfrom(256)
            except socket.timeout:
                break
            except Exception:
                break
            if data.startswith(MAGIC):
                ip = data[len(MAGIC):].decode(errors="ignore") or addr[0]
                udp.close()
                return ip
        udp.close()
        return None

    def _join_thread(self, host_ip):
        try:
            ip = host_ip or self._discover()
            if not ip:
                if self.error is None:
                    self.error = "No host found on the network."
                return
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((ip, GAME_PORT))
            sock.settimeout(None)
            self._sock = sock
            self.connected = True
            self._recv_loop()
        except Exception as exc:
            self.error = str(exc)

    # ------------------------------------------------------------- framed I/O
    def send(self, payload):
        if self._sock is None:
            return
        try:
            self._sock.sendall(struct.pack(">I", len(payload)) + payload)
        except Exception as exc:
            self.error = str(exc)
            self.connected = False

    def _recv_all(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("peer closed the connection")
            buf += chunk
        return buf

    def _recv_loop(self):
        try:
            while not self._stop.is_set():
                (length,) = struct.unpack(">I", self._recv_all(4))
                self.inbox.put(self._recv_all(length))
        except Exception as exc:
            self.error = str(exc)
            self.connected = False

    def poll(self):
        try:
            return self.inbox.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self._stop.set()
        self._beacon_stop.set()
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
