# src/utils/discovery.py
import socket
import threading
import time
from src.config import MDNS_SERVICE_TYPE, APP_NAME

class PeerDiscovery:
    def __init__(self, on_peer_found=None, on_peer_lost=None):
        self.on_peer_found = on_peer_found
        self.on_peer_lost = on_peer_lost
        self.zeroconf = None
        self.browser = None
        self.service_info = None
        self.peers = {}  # ip:port -> info dict

    def start_advertising(self, device_name, ip_address, port, use_tls=True):
        """Broadcast this device via mDNS Zeroconf to the local Wi-Fi / subnet."""
        try:
            from zeroconf import Zeroconf, ServiceInfo
            self.zeroconf = self.zeroconf or Zeroconf()

            desc = {
                "name": device_name,
                "tls": "1" if use_tls else "0",
                "app": APP_NAME,
            }

            # Service name format: DeviceName._localdrop._tcp.local.
            clean_name = "".join(c for c in device_name if c.isalnum() or c in ("-", "_", " ")).strip()
            service_name = f"{clean_name} ({ip_address}).{MDNS_SERVICE_TYPE}"

            self.service_info = ServiceInfo(
                MDNS_SERVICE_TYPE,
                service_name,
                addresses=[socket.inet_aton(ip_address)],
                port=port,
                properties=desc,
                server=f"{socket.gethostname()}.local.",
            )

            self.zeroconf.register_service(self.service_info)
            print(f"[mDNS] Registered service: {service_name} at {ip_address}:{port}")
        except Exception as e:
            print(f"[mDNS] Failed to register service: {e}")

    def start_browsing(self):
        """Continuously search for other LocalDrop instances on the network."""
        try:
            from zeroconf import Zeroconf, ServiceBrowser

            self.zeroconf = self.zeroconf or Zeroconf()

            class Listener:
                def __init__(outer_self):
                    self.outer = outer_self

                def add_service(outer_self, zc, type_, name):
                    info = zc.get_service_info(type_, name)
                    if info and info.addresses:
                        ip = socket.inet_ntoa(info.addresses[0])
                        port = info.port
                        tls = info.properties.get(b"tls", b"0") == b"1"
                        dev_name = info.properties.get(b"name", b"LocalDrop Peer").decode("utf-8", errors="ignore")

                        key = f"{ip}:{port}"
                        peer = {
                            "name": dev_name,
                            "ip": ip,
                            "port": port,
                            "tls": tls,
                            "key": key,
                        }
                        self.peers[key] = peer
                        if self.on_peer_found:
                            self.on_peer_found(peer)

                def update_service(outer_self, zc, type_, name):
                    outer_self.add_service(zc, type_, name)

                def remove_service(outer_self, zc, type_, name):
                    # Remove from peers
                    for key, p in list(self.peers.items()):
                        if name.startswith(p["name"]):
                            del self.peers[key]
                            if self.on_peer_lost:
                                self.on_peer_lost(p)

            self.browser = ServiceBrowser(self.zeroconf, MDNS_SERVICE_TYPE, Listener())
        except Exception as e:
            print(f"[mDNS] Failed to browse services: {e}")

    def stop(self):
        """Unregister service and close browser."""
        try:
            if self.zeroconf and self.service_info:
                self.zeroconf.unregister_service(self.service_info)
            if self.browser:
                self.browser.cancel()
            if self.zeroconf:
                self.zeroconf.close()
        except Exception:
            pass
