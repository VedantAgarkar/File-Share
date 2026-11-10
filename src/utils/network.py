# src/utils/network.py
import socket

def find_free_port(start_port=8000, max_attempts=50):
    """Finds an available TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start_port

def get_available_interfaces():
    """
    Returns a list of tuples: (interface_name_or_desc, ip_address).
    Prefers Wi-Fi / LAN IPs over virtual bridge / docker IPs.
    """
    interfaces = []
    
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for link in addrs[netifaces.AF_INET]:
                    ip = link.get('addr')
                    if ip and not ip.startswith('127.'):
                        tag = iface
                        if iface.startswith(('wl', 'wi', 'enx')):
                            tag = f"Wi-Fi ({iface})"
                        elif iface.startswith(('en', 'eth')):
                            tag = f"Ethernet ({iface})"
                        elif 'docker' in iface or 'br-' in iface or 'vbox' in iface or 'virbr' in iface:
                            tag = f"Virtual ({iface})"
                        interfaces.append((tag, ip))
    except Exception:
        pass

    default_ip = get_local_ip()
    if not interfaces:
        interfaces.append(("Default LAN", default_ip))
    else:
        def sort_priority(item):
            tag = item[0].lower()
            if "wi-fi" in tag or "wlan" in tag:
                return 0
            if "ethernet" in tag:
                return 1
            if "virtual" in tag or "docker" in tag:
                return 3
            return 2
        interfaces.sort(key=sort_priority)

    return interfaces

def get_local_ip():
    """Returns primary LAN IP via outbound UDP socket probe."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return "127.0.0.1"
