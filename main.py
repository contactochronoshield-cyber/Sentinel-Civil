import os
import sys
import time
import json
import sqlite3
import platform
import subprocess
import logging
import urllib.request
import urllib.parse
from logging.handlers import RotatingFileHandler

TYPE = "CIVIL"
VERSION = "2.0.0-COMMUNITY"

HOME = os.path.expanduser("~")
BASE_DIR = os.path.join(HOME, "sentinel_public")
LOG_FILE = os.path.join(BASE_DIR, "sentinel_civic.log")
DB_FILE = os.path.join(BASE_DIR, "sentinel.db")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

os.makedirs(BASE_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "node_name": platform.node() or "sentinel-node",
    "check_interval_seconds": 10,
    "interfaces_to_check": ["wlan0", "rmnet0", "rmnet_data0"],
    "wan_target": "1.1.1.1",
    "wan_ping_count": 3,
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "notify_levels": ["CRITICAL", "WARNING"]
    },
    "central_reporting": {
        "enabled": False,
        "url": "http://100.64.0.1:8000/api/sentinel/report",
        "token": ""
    },
    "signal_monitoring": {
        "enabled": True,
        "rssi_warning_threshold": -75,
        "rssi_critical_threshold": -85,
        "trend_drop_dbm": 15,
        "trend_window_cycles": 6
    },
    "vpn_monitoring": {
        "enabled": True,
        "manual_interfaces": [],
        "handshake_stale_seconds": 180,
        "latency_compare_target": "1.1.1.1"
    },
    "lan_monitoring": {
        "enabled": True,
        "known_ips": [],
        "auto_baseline": True,
        "sweep_interval_cycles": 6
    },
    "topology": {
        "enabled": True,
        "gateway_ip": "",
        "snapshot_interval_cycles": 6
    },
    "cpe_security": {
        "enabled": True,
        "scan_interval_cycles": 12,
        "risky_ports": [21, 23, 7547],
        "admin_ports": [80, 443, 8080],
        "trusted_dns": ["1.1.1.1", "8.8.8.8", "8.8.4.4", "9.9.9.9"]
    },
    "log_rotation": {
        "max_bytes": 2097152,
        "backup_count": 3
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"\033[1;33m[!] Config creado en {CONFIG_FILE} — editalo y volvé a correr.\033[0m")
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    merged = {**DEFAULT_CONFIG, **cfg}
    merged["telegram"] = {**DEFAULT_CONFIG["telegram"], **cfg.get("telegram", {})}
    merged["central_reporting"] = {**DEFAULT_CONFIG["central_reporting"], **cfg.get("central_reporting", {})}
    merged["signal_monitoring"] = {**DEFAULT_CONFIG["signal_monitoring"], **cfg.get("signal_monitoring", {})}
    merged["vpn_monitoring"] = {**DEFAULT_CONFIG["vpn_monitoring"], **cfg.get("vpn_monitoring", {})}
    merged["lan_monitoring"] = {**DEFAULT_CONFIG["lan_monitoring"], **cfg.get("lan_monitoring", {})}
    merged["topology"] = {**DEFAULT_CONFIG["topology"], **cfg.get("topology", {})}
    merged["cpe_security"] = {**DEFAULT_CONFIG["cpe_security"], **cfg.get("cpe_security", {})}
    merged["log_rotation"] = {**DEFAULT_CONFIG["log_rotation"], **cfg.get("log_rotation", {})}
    return merged

CONFIG = load_config()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando config.json: {e}")


logger = logging.getLogger("SentinelCivic")
logger.setLevel(logging.INFO)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=CONFIG["log_rotation"]["max_bytes"],
    backupCount=CONFIG["log_rotation"]["backup_count"],
    encoding="utf-8"
)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node_name TEXT NOT NULL,
            level TEXT NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node_name TEXT NOT NULL,
            cpu_pct REAL,
            ram_pct REAL,
            wan_loss_pct REAL,
            wan_latency_ms REAL,
            wifi_rssi INTEGER
        )
    """)
    try:
        cur.execute("ALTER TABLE metrics ADD COLUMN wifi_rssi INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def db_insert_event(level, category, message):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events (timestamp, node_name, level, category, message) VALUES (datetime('now','localtime'), ?, ?, ?, ?)",
            (CONFIG["node_name"], level, category, message)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error escribiendo evento en SQLite: {e}")

def db_insert_metric(cpu_pct, ram_pct, wan_loss_pct, wan_latency_ms, wifi_rssi):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO metrics (timestamp, node_name, cpu_pct, ram_pct, wan_loss_pct, wan_latency_ms, wifi_rssi) VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?, ?)",
            (CONFIG["node_name"], cpu_pct, ram_pct, wan_loss_pct, wan_latency_ms, wifi_rssi)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error escribiendo métrica en SQLite: {e}")

def send_telegram(text):
    tg = CONFIG.get("telegram", {})
    if not tg.get("enabled"):
        return
    token = tg.get("bot_token")
    chat_id = tg.get("chat_id")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.error(f"Error enviando notificación Telegram: {e}")

def send_central_report(events=None, metrics=None):
    cr = CONFIG.get("central_reporting", {})
    if not cr.get("enabled"):
        return
    url = cr.get("url")
    token = cr.get("token")
    if not url or not token:
        return
    payload = {
        "node_name": CONFIG["node_name"],
        "events": events or [],
        "metrics": metrics or []
    }
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.error(f"Error reportando al servidor central: {e}")

def get_wifi_signal():
    """
    Devuelve un dict {rssi, ssid, link_speed_mbps} o None si no se pudo leer.
    Requiere el paquete termux-api instalado (pkg install termux-api) y la
    app Termux:API en el teléfono.
    """
    try:
        output = subprocess.check_output(
            ["termux-wifi-connectioninfo"], stderr=subprocess.DEVNULL, timeout=5
        ).decode("utf-8")
        data = json.loads(output)
        rssi = data.get("rssi")
        if rssi is None or rssi == 0:
            return None
        return {
            "rssi": int(rssi),
            "ssid": data.get("ssid", "?"),
            "link_speed_mbps": data.get("link_speed_mbps")
        }
    except Exception:
        return None

# ---------------------------------------------------------------------------
# AUDITORIA DE TUNEL VPN - WireGuard, Tailscale, o cualquier tun*
# ---------------------------------------------------------------------------
def get_tunnel_interfaces(manual_list=None):
    """Detecta interfaces de tunel activas (wg*, tailscale*, tun*, utun*)."""
    if manual_list:
        return manual_list
    try:
        output = subprocess.check_output(
            "ip -o link show 2>/dev/null | awk -F': ' '{print $2}'",
            shell=True
        ).decode("utf-8")
        names = [n.strip() for n in output.split("\n") if n.strip()]
        prefixes = ("wg", "tailscale", "tun", "utun")
        return [n for n in names if n.lower().startswith(prefixes)]
    except Exception:
        return []

def get_wg_handshake_age(iface):
    """Devuelve segundos desde el ultimo handshake de WireGuard, o None."""
    try:
        output = subprocess.check_output(
            f"wg show {iface} latest-handshakes 2>/dev/null",
            shell=True
        ).decode("utf-8").strip()
        if not output:
            return None
        parts = output.split()
        if len(parts) < 2:
            return None
        ts = int(parts[1])
        if ts == 0:
            return None
        return int(time.time()) - ts
    except Exception:
        return None

def ping_via_interface(iface, target, count=2):
    """Latencia promedio en ms haciendo ping a traves de una interfaz especifica."""
    try:
        cmd = f"ping -I {iface} -c {count} -W 2 {target} 2>/dev/null"
        output = subprocess.check_output(cmd, shell=True).decode("utf-8")
        for line in output.split("\n"):
            if "min/avg/max" in line or "rtt" in line:
                if "/" in line:
                    return float(line.split("=")[-1].split("/")[1])
        return None
    except Exception:
        return None

# ---------------------------------------------------------------------------
# INVENTARIO LAN - deteccion de dispositivos desconocidos en la red
# ---------------------------------------------------------------------------
def get_local_subnet_prefix():
    try:
        output = subprocess.check_output("ifconfig 2>/dev/null", shell=True).decode("utf-8")
        blocks = output.split("\n\n")
        for block in blocks:
            if block.strip().startswith("wlan0:"):
                for line in block.split("\n"):
                    parts = line.strip().split()
                    if "inet" in parts:
                        idx = parts.index("inet")
                        if idx + 1 < len(parts):
                            ip = parts[idx + 1]
                            p = ip.split(".")
                            if len(p) == 4:
                                return ".".join(p[:3])
        return None
    except Exception:
        return None

def _ping_host(ip):
    try:
        subprocess.check_output(
            f"ping -c 1 -W 1 {ip} 2>/dev/null", shell=True
        )
        return ip
    except Exception:
        return None

def get_lan_devices():
    import concurrent.futures
    prefix = get_local_subnet_prefix()
    if not prefix:
        return []
    hosts = [f"{prefix}.{i}" for i in range(1, 255)]
    found = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
            for result in executor.map(_ping_host, hosts):
                if result:
                    found.append({"ip": result})
    except Exception:
        pass
    return found

# ---------------------------------------------------------------------------
# TOPOLOGIA DE RED - mapa de dependencias Internet -> Gateway -> VPN -> LAN
# ---------------------------------------------------------------------------
TOPOLOGY_FILE = os.path.join(BASE_DIR, "topology.json")

def guess_gateway_ip(lan_prefix):
    if not lan_prefix:
        return None
    return f"{lan_prefix}.1"

def save_topology_snapshot(snapshot):
    try:
        with open(TOPOLOGY_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando topology.json: {e}")

def print_topology_tree(snapshot):
    wan = snapshot["wan"]
    wan_icon = "\033[1;32m●\033[0m" if wan["status"] == "up" else "\033[1;31m●\033[0m"
    print(f"  {wan_icon} Internet (WAN)  [{wan['latency_ms']}ms, {wan['loss_pct']}% loss]")

    gw = snapshot["gateway"]
    gw_icon = "\033[1;32m●\033[0m" if gw["ip"] else "\033[2m○\033[0m"
    gw_label = gw["ip"] if gw["ip"] else "desconocido"
    print(f"  └─ {gw_icon} Gateway ({gw_label})")

    tunnels = snapshot["vpn_tunnels"]
    if tunnels:
        for t in tunnels:
            t_icon = "\033[1;32m●\033[0m" if t["healthy"] else "\033[1;31m●\033[0m"
            print(f"      └─ {t_icon} Tunel VPN: {t['iface']}")
    else:
        print(f"      └─ \033[2m○ Sin tuneles VPN activos\033[0m")

    lan = snapshot["lan"]
    unknown_tag = f"\033[1;31m{lan['unknown']} desconocido(s)\033[0m" if lan["unknown"] > 0 else "0 desconocidos"
    print(f"          └─ Red Local: {lan['known']} conocido(s), {unknown_tag}")

# ---------------------------------------------------------------------------
# CPE SECURITY MONITORING - clasificacion de riesgo del gateway/router
# ---------------------------------------------------------------------------
RISKY_PORT_NAMES = {21: "FTP", 23: "Telnet", 7547: "TR-069/CWMP"}

def scan_gateway_ports(gateway_ip, ports, timeout=1.0):
    import socket
    open_ports = []
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            result = s.connect_ex((gateway_ip, port))
            s.close()
            if result == 0:
                open_ports.append(port)
        except Exception:
            pass
    return open_ports

def get_device_dns_servers():
    dns = []
    for prop in ["net.dns1", "net.dns2"]:
        try:
            val = subprocess.check_output(f"getprop {prop} 2>/dev/null", shell=True).decode("utf-8").strip()
            if val:
                dns.append(val)
        except Exception:
            pass
    return dns

def classify_cpe_risk(open_ports, dns_servers, gateway_ip, cfg):
    risky_ports = cfg.get("risky_ports", [21, 23, 7547])
    admin_ports = cfg.get("admin_ports", [80, 443, 8080])
    trusted_dns = cfg.get("trusted_dns", [])

    risky_found = [p for p in open_ports if p in risky_ports]
    admin_found = [p for p in open_ports if p in admin_ports]

    dns_suspicious = False
    if gateway_ip and dns_servers:
        dns_suspicious = all(
            d != gateway_ip and d not in trusted_dns for d in dns_servers
        )

    reasons = []
    if risky_found:
        names = [RISKY_PORT_NAMES.get(p, str(p)) for p in risky_found]
        reasons.append(f"Puerto(s) de riesgo abiertos: {', '.join(names)}")
    if dns_suspicious:
        reasons.append(f"DNS inesperado (no es el gateway ni uno confiable): {', '.join(dns_servers)}")

    if risky_found or dns_suspicious:
        return "HIGH RISK", reasons
    if admin_found:
        return "COMPENSATABLE", [f"Panel de administracion expuesto en puerto(s): {admin_found}"]
    return "SUPPORTED", []

# ---------------------------------------------------------------------------
# KERNEL
# ---------------------------------------------------------------------------
class CivicKernel:
    def __init__(self):
        self.running = True
        self.tracked_interfaces = {}
        self.rssi_history = []  # ventana móvil para detectar caídas rápidas

    def log_and_print(self, level, category, text_clean, text_ansi, notify=True):
        print(text_ansi)
        if level == "INFO":
            logger.info(text_clean)
        elif "WARN" in level:
            logger.warning(text_clean)
        elif "CRIT" in level:
            logger.critical(text_clean)

        db_insert_event(level, category, text_clean)

        if notify and level in CONFIG["telegram"].get("notify_levels", []):
            icon = "🔴" if "CRIT" in level else "🟡"
            send_telegram(f"{icon} <b>[{level}] {CONFIG['node_name']}</b>\n{category}: {text_clean}")

        send_central_report(events=[{
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "category": category,
            "message": text_clean
        }])

    def boot(self):
        os.system('clear')
        init_db()
        self.log_and_print("INFO", "SYSTEM", f"Kernel Sentinel Civic-Core v{VERSION} iniciado.",
                           f"\033[1;32m[●] SENTINEL CIVIC-CORE v{VERSION} ACTIVE\033[0m", notify=False)
        self.log_and_print("INFO", "SYSTEM", f"Nodo: {CONFIG['node_name']} | DB: {DB_FILE}",
                           f"\033[1;34m[i] Nodo: {CONFIG['node_name']} | Persistencia SQLite activa\033[0m", notify=False)

        if CONFIG["telegram"].get("enabled"):
            print("\033[1;34m[i] Notificaciones Telegram: ACTIVAS\033[0m")
            send_telegram(f"🟢 <b>{CONFIG['node_name']}</b> — Sentinel Civic-Core v{VERSION} en línea.")
        else:
            print("\033[2m[i] Notificaciones Telegram: desactivadas (configurar en config.json)\033[0m")

        if CONFIG["central_reporting"].get("enabled"):
            print(f"\033[1;34m[i] Reporte central: ACTIVO -> {CONFIG['central_reporting']['url']}\033[0m")
        else:
            print("\033[2m[i] Reporte central: desactivado (configurar en config.json)\033[0m")

        if CONFIG["signal_monitoring"].get("enabled"):
            test_signal = get_wifi_signal()
            if test_signal:
                print(f"\033[1;34m[i] Monitoreo de señal WiFi: ACTIVO (RSSI actual: {test_signal['rssi']} dBm)\033[0m")
            else:
                print("\033[2m[i] Monitoreo de señal: activado pero sin datos (¿instalaste termux-api?)\033[0m")
        time.sleep(1)

        try:
            self.monitor_loop()
        except KeyboardInterrupt:
            print("\n\033[1;31m[!] Monitoreo interrumpido por el operador.\033[0m")
            self.shutdown()

    def monitor_loop(self):
        ciclo = 1
        interval = CONFIG.get("check_interval_seconds", 10)
        while self.running:
            print(f"\n\033[1;33m--- [ CIVIC CORE KERNEL: CICLO #{ciclo} | {CONFIG['node_name']} ] ---\033[0m")
            cpu, ram = self.check_environment_and_memory()
            self.check_network_interfaces()
            loss, latency = self.check_layer3_telemetry()
            rssi = self.check_signal_quality()
            self.check_vpn_tunnels()
            self.check_lan_devices()
            self.build_and_print_topology(cpu, ram, loss, latency)
            self.check_cpe_security(getattr(self, 'last_gateway_ip', None))

            db_insert_metric(cpu, ram, loss, latency, rssi)
            send_central_report(metrics=[{
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "cpu_pct": cpu,
                "ram_pct": ram,
                "wan_loss_pct": loss,
                "wan_latency_ms": latency,
                "wifi_rssi": rssi
            }])

            print(f"\033[2m[i] Próximo análisis en {interval} segundos... (Ctrl+C para interrumpir)\033[0m")
            time.sleep(interval)
            ciclo += 1

    def check_environment_and_memory(self):
        cpu, ram = None, None
        try:
            print("\033[32m[+] Diagnóstico del Entorno de Host:\033[0m")
            print(f"  > Arquitectura CPU : {platform.machine()}")
            print(f"  > Sistema Operativo: {platform.system()} {platform.release()}")
        except Exception as e:
            logger.error(f"Error en diagnóstico de entorno: {e}")

        print("\033[32m[+] Estado de Memoria de Subcapa:\033[0m")
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    meminfo[parts[0].rstrip(':')] = int(parts[1])
            total = meminfo.get("MemTotal", 0)
            avail = meminfo.get("MemAvailable", 0)
            if total > 0:
                ram = round(((total - avail) / total) * 100, 2)
                print(f"  > RAM en uso: {ram}% ({(total-avail)//1024} MB / {total//1024} MB)")
        except Exception:
            if os.system("command -v free > /dev/null 2>&1") == 0:
                os.system("free -m | grep -E 'Mem|Total'")
            else:
                print("  \033[1;33m[!] Alerta: No se pudo leer memoria en este entorno.\033[0m")

        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline().strip().split()[1:]
            campos = [float(x) for x in line]
            id_ant, tot_ant = campos[3], sum(campos)
            time.sleep(0.05)
            with open('/proc/stat', 'r') as f:
                line2 = f.readline().strip().split()[1:]
            campos2 = [float(x) for x in line2]
            dif_tot = sum(campos2) - tot_ant
            if dif_tot > 0:
                cpu = round((1.0 - ((campos2[3] - id_ant) / dif_tot)) * 100, 2)
                print(f"  > CPU en uso: {cpu}%")
        except Exception:
            pass

        return cpu, ram

    def check_network_interfaces(self):
        print("\033[32m[+] Mapeo de Interfaces Críticas (Anti-Tamper):\033[0m")
        if os.system("command -v ip > /dev/null 2>&1") != 0:
            print("  \033[1;33m[!] Alerta: Binario 'ip' no disponible para verificación de interfaz.\033[0m")
            return

        interfaces_to_check = CONFIG.get("interfaces_to_check", ["wlan0", "rmnet0", "rmnet_data0"])

        for iface in interfaces_to_check:
            try:
                cmd = f"ip -4 addr show {iface} 2>/dev/null | grep -E 'inet ' | awk '{{print $2}}' | cut -d/ -f1"
                current_ip = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()

                if current_ip:
                    print(f"  > Interfaz [\033[1;36m{iface}\033[0m] -> IP Asignada: {current_ip}")

                    if iface in self.tracked_interfaces and self.tracked_interfaces[iface] != current_ip:
                        old_ip = self.tracked_interfaces[iface]
                        msg_clean = f"ALERTA MANIPULACIÓN INTERFAZ: {iface} cambió de {old_ip} a {current_ip}"
                        msg_ansi = f"  \033[1;31m[CRITICAL ALERTA] ¡Modificación de Interfaz {iface}! {old_ip} -> {current_ip}\033[0m"
                        self.log_and_print("CRITICAL", "NETWORK", msg_clean, msg_ansi)

                    self.tracked_interfaces[iface] = current_ip
            except Exception as e:
                logger.error(f"Error analizando interfaz {iface}: {e}")

    def check_layer3_telemetry(self):
        print("\033[32m[+] Telemetría Activa L3 (WAN Verification):\033[0m")
        target = CONFIG.get("wan_target", "1.1.1.1")
        count = CONFIG.get("wan_ping_count", 3)
        param = f"-c {count}" if platform.system().lower() != "windows" else f"-n {count}"

        loss_val, latency_val = None, None
        try:
            cmd = f"ping {param} -W 2 {target} 2>/dev/null"
            output = subprocess.check_output(cmd, shell=True).decode('utf-8')

            loss = "0%"
            for line in output.split('\n'):
                if "packet loss" in line:
                    loss = line.split('%')[0].split()[-1] + "%"
            loss_val = float(loss.replace('%', ''))

            avg_latency = "N/A"
            if "rtt" in output or "min/avg/max" in output:
                tail = output.split('\n')[-2] if output.split('\n')[-1] == "" else output.split('\n')[-1]
                if "/" in tail:
                    avg_latency = tail.split('/')[4]
                    latency_val = float(avg_latency)

            latency_display = f"{avg_latency} ms" if latency_val is not None else "N/A"
            print(f"  > Enlace WAN íntegro ({target}) | Pérdida: \033[1;32m{loss}\033[0m | Latencia Promedio: \033[1;36m{latency_display}\033[0m")
            if loss_val and loss_val > 0:
                msg = f"Degradación de enlace: Packet Loss del {loss} detectado en WAN."
                self.log_and_print("WARNING", "WAN", msg, f"  \033[1;33m[WARN] {msg}\033[0m")

        except Exception:
            msg_clean = "Pérdida de conectividad WAN total o bloqueo ICMP perimetral."
            msg_ansi = "  \033[1;31m[ALERT] Canal WAN inaccesible. Interfaces sin salida a internet.\033[0m"
            self.log_and_print("WARNING", "WAN", msg_clean, msg_ansi)
            loss_val = 100.0

        return loss_val, latency_val

    def check_signal_quality(self):
        """
        Lee el RSSI actual, lo compara contra umbrales absolutos y detecta
        caídas rápidas dentro de una ventana móvil de ciclos — pensado para
        avisar ANTES de que el enlace se caiga del todo (uso WISP).
        """
        sm = CONFIG.get("signal_monitoring", {})
        if not sm.get("enabled"):
            return None

        print("\033[32m[+] Calidad de Señal (Anti-Degradación):\033[0m")
        signal = get_wifi_signal()
        if not signal:
            print("  \033[2m[i] Sin datos de señal (termux-api no disponible o sin conexión WiFi).\033[0m")
            return None

        rssi = signal["rssi"]
        print(f"  > SSID: {signal['ssid']} | RSSI: \033[1;36m{rssi} dBm\033[0m | Velocidad: {signal.get('link_speed_mbps', '?')} Mbps")

        warn_th = sm.get("rssi_warning_threshold", -75)
        crit_th = sm.get("rssi_critical_threshold", -85)

        if rssi <= crit_th:
            msg = f"Señal CRÍTICA: {rssi} dBm (umbral crítico: {crit_th} dBm). Riesgo alto de caída de enlace."
            self.log_and_print("CRITICAL", "SIGNAL", msg, f"  \033[1;31m[CRITICAL] {msg}\033[0m")
        elif rssi <= warn_th:
            msg = f"Señal débil: {rssi} dBm (umbral de alerta: {warn_th} dBm)."
            self.log_and_print("WARNING", "SIGNAL", msg, f"  \033[1;33m[WARN] {msg}\033[0m")

        window = sm.get("trend_window_cycles", 6)
        drop_threshold = sm.get("trend_drop_dbm", 15)
        self.rssi_history.append(rssi)
        if len(self.rssi_history) > window:
            self.rssi_history.pop(0)

        if len(self.rssi_history) == window:
            drop = self.rssi_history[0] - self.rssi_history[-1]
            if drop >= drop_threshold:
                msg = (f"Caída rápida de señal detectada: {self.rssi_history[0]} dBm -> {rssi} dBm "
                       f"en {window} ciclos (~{window * CONFIG.get('check_interval_seconds', 10)}s). "
                       f"Posible antena desalineada u obstrucción nueva.")
                self.log_and_print("WARNING", "SIGNAL", msg, f"  \033[1;33m[WARN] {msg}\033[0m")
                self.rssi_history = []

        return rssi

    def check_vpn_tunnels(self):
        vm = CONFIG.get("vpn_monitoring", {})
        if not vm.get("enabled"):
            return

        ifaces = get_tunnel_interfaces(vm.get("manual_interfaces") or None)
        if not ifaces:
            return

        print("\033[32m[+] Auditoria de Tunel VPN:\033[0m")
        stale_th = vm.get("handshake_stale_seconds", 180)
        target = vm.get("latency_compare_target", "1.1.1.1")

        for iface in ifaces:
            print(f"  > Tunel detectado: \033[1;36m{iface}\033[0m")

            if iface.lower().startswith("wg"):
                age = get_wg_handshake_age(iface)
                if age is None:
                    print("    - Handshake: sin datos (wg-tools no disponible o sin peers)")
                else:
                    print(f"    - Ultimo handshake: hace {age}s")
                    if age > stale_th:
                        msg = f"Tunel {iface}: handshake WireGuard sin renovar hace {age}s (umbral: {stale_th}s). Posible tunel caido."
                        self.log_and_print("WARNING", "VPN", msg, f"    \033[1;33m[WARN] {msg}\033[0m")

            latency = ping_via_interface(iface, target)
            if latency is not None:
                print(f"    - Latencia via tunel ({target}): {latency} ms")
            else:
                print(f"    - Latencia via tunel: sin respuesta (tunel posiblemente caido)")

    def check_lan_devices(self):
        lm = CONFIG.get("lan_monitoring", {})
        if not lm.get("enabled"):
            return

        if not hasattr(self, "lan_cycle_counter"):
            self.lan_cycle_counter = 0
        self.lan_cycle_counter += 1

        interval = lm.get("sweep_interval_cycles", 6)
        if self.lan_cycle_counter % interval != 1:
            return

        print("\033[32m[+] Barrido de Red Local (sin root, base IP):\033[0m")
        devices = get_lan_devices()
        self.last_lan_devices = devices
        if not devices:
            print("  \033[2m[i] Sin respuesta en la subred (¿wlan0 sin IP asignada?).\033[0m")
            return

        known = set(lm.get("known_ips", []))

        if not known and lm.get("auto_baseline", True) and not getattr(self, "lan_baselined", False):
            new_known = sorted(set(d["ip"] for d in devices))
            lm["known_ips"] = new_known
            CONFIG["lan_monitoring"] = lm
            save_config(CONFIG)
            self.lan_baselined = True
            msg = f"Baseline LAN creado con {len(new_known)} IP(s) conocida(s)."
            self.log_and_print("INFO", "LAN", msg, f"  \033[32m[+] {msg}\033[0m", notify=False)
            return

        print(f"  > {len(devices)} dispositivo(s) respondieron en la subred.")
        if not hasattr(self, "alerted_ips"):
            self.alerted_ips = set()

        for d in devices:
            ip = d["ip"]
            tag = "conocido" if ip in known else "\033[1;31mDESCONOCIDO\033[0m"
            print(f"    > {ip}  [{tag}]")

            if ip not in known and ip not in self.alerted_ips:
                msg = f"Dispositivo DESCONOCIDO respondiendo en la red: IP {ip} (fuera del baseline)."
                self.log_and_print("CRITICAL", "LAN_SECURITY", msg, f"    \033[1;31m[CRITICAL] {msg}\033[0m")
                self.alerted_ips.add(ip)

    def build_and_print_topology(self, cpu, ram, wan_loss, wan_latency):
        tp = CONFIG.get("topology", {})
        if not tp.get("enabled"):
            return

        if not hasattr(self, "topo_cycle_counter"):
            self.topo_cycle_counter = 0
        self.topo_cycle_counter += 1
        interval = tp.get("snapshot_interval_cycles", 6)
        if self.topo_cycle_counter % interval != 1:
            return

        lm = CONFIG.get("lan_monitoring", {})
        lan_prefix = get_local_subnet_prefix()
        gateway_ip = tp.get("gateway_ip") or guess_gateway_ip(lan_prefix)
        self.last_gateway_ip = gateway_ip

        known_ips = set(lm.get("known_ips", []))
        last_lan_devices = getattr(self, "last_lan_devices", [])
        lan_known = sum(1 for d in last_lan_devices if d.get("ip") in known_ips)
        lan_unknown = sum(1 for d in last_lan_devices if d.get("ip") not in known_ips)

        vm = CONFIG.get("vpn_monitoring", {})
        tunnel_ifaces = get_tunnel_interfaces(vm.get("manual_interfaces") or None) if vm.get("enabled") else []
        tunnels_info = []
        for iface in tunnel_ifaces:
            healthy = True
            if iface.lower().startswith("wg"):
                age = get_wg_handshake_age(iface)
                stale_th = vm.get("handshake_stale_seconds", 180)
                healthy = age is not None and age <= stale_th
            tunnels_info.append({"iface": iface, "healthy": healthy})

        snapshot = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "node_name": CONFIG["node_name"],
            "wan": {
                "status": "up" if (wan_loss is not None and wan_loss < 100) else "down",
                "latency_ms": wan_latency,
                "loss_pct": wan_loss
            },
            "gateway": {"ip": gateway_ip},
            "vpn_tunnels": tunnels_info,
            "lan": {"known": lan_known, "unknown": lan_unknown}
        }

        save_topology_snapshot(snapshot)
        print("\033[32m[+] Mapa de Topologia de Red:\033[0m")
        print_topology_tree(snapshot)

    def check_cpe_security(self, gateway_ip):
        cs = CONFIG.get("cpe_security", {})
        if not cs.get("enabled") or not gateway_ip:
            return

        if not hasattr(self, "cpe_cycle_counter"):
            self.cpe_cycle_counter = 0
        self.cpe_cycle_counter += 1
        interval = cs.get("scan_interval_cycles", 12)
        if self.cpe_cycle_counter % interval != 1:
            return

        print("\033[32m[+] CPE Security Monitoring (Gateway):\033[0m")
        all_ports = list(set(cs.get("risky_ports", []) + cs.get("admin_ports", [])))
        open_ports = scan_gateway_ports(gateway_ip, all_ports)
        dns_servers = get_device_dns_servers()

        risk, reasons = classify_cpe_risk(open_ports, dns_servers, gateway_ip, cs)
        self.last_cpe_risk = risk

        color = {"SUPPORTED": "\033[1;32m", "COMPENSATABLE": "\033[1;33m", "HIGH RISK": "\033[1;31m"}.get(risk, "")
        print(f"  > Clasificacion: {color}{risk}\033[0m")
        print(f"  > Puertos abiertos detectados: {open_ports if open_ports else 'ninguno'}")
        print(f"  > DNS del dispositivo: {dns_servers if dns_servers else 'no disponible'}")

        if risk == "HIGH RISK":
            for r in reasons:
                msg = f"CPE riesgo alto ({gateway_ip}): {r}"
                self.log_and_print("CRITICAL", "CPE_SECURITY", msg, f"    \033[1;31m[CRITICAL] {msg}\033[0m")
        elif risk == "COMPENSATABLE":
            for r in reasons:
                print(f"    \033[1;33m[i] {r}\033[0m")

    def shutdown(self):
        self.running = False
        self.log_and_print("INFO", "SYSTEM", "Kernel Sentinel Civic-Core cerrado de forma segura.",
                           "\033[1;32m[●] Resguardo activo. Procesos purgados de la memoria local.\033[0m", notify=False)
        if CONFIG["telegram"].get("enabled"):
            send_telegram(f"🔴 <b>{CONFIG['node_name']}</b> — Sentinel Civic-Core detenido.")
        sys.exit(0)

def signal_bar(rssi, width=20):
    """Convierte RSSI (-30 a -95 aprox) en una barra visual simple."""
    if rssi is None:
        return "[sin datos]"
    pct = max(0, min(100, int((rssi + 95) / (95 - 30) * 100)))
    filled = int(width * pct / 100)
    color = "\033[1;32m" if pct > 60 else ("\033[1;33m" if pct > 30 else "\033[1;31m")
    bar = color + "█" * filled + "\033[2m" + "░" * (width - filled) + "\033[0m"
    return f"{bar} {pct:3d}%"

def run_survey_mode():
    """
    Modo pensado para técnicos: caminá por el edificio/predio con el
    celular corriendo esto, y va mostrando en vivo la calidad de señal
    en el punto donde estás parado, más un resumen final con el mejor
    y peor punto medido. Guarda todo en un CSV para revisar después.
    Uso: python3 main.py --survey
    """
    os.system('clear')
    print(f"\033[1;35m[◎] SENTINEL SITE SURVEY MODE — v{VERSION}\033[0m")
    print("\033[2mCaminá por el sitio y observá cómo cambia la señal en cada punto.")
    print("Presioná Ctrl+C para terminar y ver el resumen.\033[0m\n")

    csv_path = os.path.join(BASE_DIR, f"survey_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    readings = []

    try:
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("timestamp,ssid,rssi_dbm,link_speed_mbps\n")

            while True:
                signal = get_wifi_signal()
                ts = time.strftime("%Y-%m-%d %H:%M:%S")

                if signal:
                    rssi = signal["rssi"]
                    readings.append(rssi)
                    f.write(f"{ts},{signal['ssid']},{rssi},{signal.get('link_speed_mbps', '')}\n")
                    f.flush()
                    print(f"\r  {ts}  {signal['ssid']:<20}  {signal_bar(rssi)}  ({rssi} dBm)   ", end="", flush=True)
                else:
                    print(f"\r  {ts}  \033[2mSin señal WiFi detectada (¿termux-api instalado?)\033[0m          ", end="", flush=True)

                time.sleep(1.5)

    except KeyboardInterrupt:
        print("\n\n\033[1;32m[✓] Survey finalizado.\033[0m")
        if readings:
            best = max(readings)
            worst = min(readings)
            avg = round(sum(readings) / len(readings), 1)
            print(f"  > Mejor punto medido : {best} dBm")
            print(f"  > Peor punto medido  : {worst} dBm")
            print(f"  > Promedio           : {avg} dBm")
            print(f"  > Lecturas totales   : {len(readings)}")
        else:
            print("  \033[1;33m[!] No se registraron lecturas de señal.\033[0m")
        print(f"\n  Datos guardados en: {csv_path}")
        sys.exit(0)

if __name__ == "__main__":
    if "--survey" in sys.argv or "survey" in sys.argv:
        run_survey_mode()
    else:
        kernel = CivicKernel()
        kernel.boot()
