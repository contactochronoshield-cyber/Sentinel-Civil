import os
import sys
import time
import platform
import subprocess
import logging
from logging.handlers import RotatingFileHandler

# CHRONO SHIELD NETWORKS - CIVIC CORE (PUBLIC VERSION)
TYPE = "CIVIL"
VERSION = "1.4.0-COMMUNITY"
LOG_DIR = os.path.expanduser("~/sentinel_public")
LOG_FILE = os.path.join(LOG_DIR, "sentinel_civic.log")

# Asegurar que el directorio de logs exista
os.makedirs(LOG_DIR, exist_ok=True)

# CONFIGURACIÓN DE LOGGING ROTATIVO PROFESIONAL (Nivel Producción)
logger = logging.getLogger("SentinelCivic")
logger.setLevel(logging.INFO)

# Rotación: Máximo 2MB por archivo, conserva hasta 3 archivos de respaldo
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class CivicKernel:
    def __init__(self):
        self.running = True
        self.tracked_interfaces = {}  # Guarda el estado de IP por interfaz individual

    def log_and_print(self, level, text_clean, text_ansi):
        """Imprime con colores en terminal y guarda en log limpio sin códigos ANSI."""
        print(text_ansi)
        if level == "INFO":
            logger.info(text_clean)
        elif "WARN" in level:
            logger.warning(text_clean)
        elif "CRIT" in level:
            logger.critical(text_clean)

    def boot(self):
        os.system('clear')
        self.log_and_print("INFO", f"Kernel Sentinel Civic-Core v{VERSION} iniciado.", 
                           f"\033[1;32m[●] SENTINEL CIVIC-CORE v{VERSION} ACTIVE\033[0m")
        self.log_and_print("INFO", f"Subsistema Log Rotativo montado en: {LOG_FILE}", 
                           f"\033[1;34m[i] Subsistema Log Rotativo activo (Max: 2MB, Backup: 3)\033[0m")
        time.sleep(1)
        
        try:
            self.monitor_loop()
        except KeyboardInterrupt:
            print("\n\033[1;31m[!] Monitoreo interrumpido por el operador.\033[0m")
            self.shutdown()

    def monitor_loop(self):
        ciclo = 1
        while self.running:
            print(f"\n\033[1;33m--- [ CIVILE CORE KERNEL: CICLE #{ciclo} ] ---\033[0m")
            self.check_environment()
            self.check_memory()
            self.check_network_interfaces()
            self.check_layer3_telemetry()
            
            print(f"\033[2m[i] Próximo análisis en 10 segundos... (Ctrl+C para interrumpir)\033[0m")
            time.sleep(10)
            ciclo += 1

    def check_environment(self):
        try:
            print("\033[32m[+] Diagnóstico del Entorno de Host:\033[0m")
            print(f"  > Arquitectura CPU : {platform.machine()}")
            print(f"  > Sistema Operativo: {platform.system()} {platform.release()}")
        except Exception as e:
            logger.error(f"Error en diagnóstico de entorno: {e}")

    def check_memory(self):
        print("\033[32m[+] Estado de Memoria de Subcapa:\033[0m")
        if os.system("command -v free > /dev/null 2>&1") == 0:
            os.system("free -m | grep -E 'Mem|Total'")
        else:
            print("  \033[1;33m[!] Alerta: Utilidad 'free' no accesible en este entorno.\033[0m")

    def check_network_interfaces(self):
        print("\033[32m[+] Mapeo de Interfaces Críticas (Anti-Tamper):\033[0m")
        if os.system("command -v ip > /dev/null 2>&1") != 0:
            print("  \033[1;33m[!] Alerta: Binario 'ip' no disponible para verificación de interfaz.\033[0m")
            return

        # Analizar de forma independiente interfaces clave: wlan0 (WiFi) y rmnet (Móvil/5G)
        interfaces_to_check = ['wlan0', 'rmnet0', 'rmnet_data0']
        
        for iface in interfaces_to_check:
            try:
                # Extraer IP de la interfaz específica de forma limpia
                cmd = f"ip -4 addr show {iface} 2>/dev/null | grep -E 'inet ' | awk '{{print $2}}' | cut -d/ -f1"
                current_ip = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
                
                if current_ip:
                    print(f"  > Interfaz [\033[1;36m{iface}\033[0m] -> IP Asignada: {current_ip}")
                    
                    # Detectar si la IP cambió respecto al ciclo anterior
                    if iface in self.tracked_interfaces and self.tracked_interfaces[iface] != current_ip:
                        old_ip = self.tracked_interfaces[iface]
                        msg_clean = f"ALERTA MANIPULACIÓN INTERFAZ: {iface} cambió de {old_ip} a {current_ip}"
                        msg_ansi = f"  \033[1;31m[CRITICAL ALERTA] ¡Modificación de Interfaz {iface}! {old_ip} -> {current_ip}\033[0m"
                        self.log_and_print("CRITICAL", msg_clean, msg_ansi)
                        
                    self.tracked_interfaces[iface] = current_ip
            except Exception as e:
                logger.error(f"Error analizando interfaz {iface}: {e}")

    def check_layer3_telemetry(self):
        print("\033[32m[+] Telemetría Activa L3 (WAN Verification):\033[0m")
        target = "1.1.1.1"
        param = "-c 3" if platform.system().lower() != "windows" else "-n 3"
        
        try:
            # Lanzamos 3 paquetes para calcular latencia y packet loss de manera real
            cmd = f"ping {param} -W 2 {target} 2>/dev/null"
            output = subprocess.check_output(cmd, shell=True).decode('utf-8')
            
            # Extraer porcentaje de pérdida de paquetes
            loss = "0%"
            for line in output.split('\n'):
                if "packet loss" in line:
                    loss = line.split('%')[0].split()[-1] + "%"
            
            # Extraer latencia promedio (rtt min/avg/max/mdev)
            avg_latency = "N/A"
            if "rtt" in output or "min/avg/max" in output:
                tail = output.split('\n')[-2] if output.split('\n')[-1] == "" else output.split('\n')[-1]
                if "/" in tail:
                    avg_latency = tail.split('/')[4] + " ms"

            print(f"  > Enlace WAN íntegro ({target}) | Pérdida: \033[1;32m{loss}\033[0m | Latencia Promedio: \033[1;36m{avg_latency}\033[0m")
            if int(loss.replace('%', '')) > 0:
                logger.warning(f"Degradación de enlace: Packet Loss del {loss} detectado en WAN.")
                
        except Exception:
            msg_clean = "Pérdida de conectividad WAN total o bloqueo ICMP perimetral."
            msg_ansi = "  \033[1;31m[ALERT] Canal WAN inaccesible. Interfaces sin salida a internet.\033[0m"
            self.log_and_print("WARNING", msg_clean, msg_ansi)

    def shutdown(self):
        self.running = False
        self.log_and_print("INFO", "Kernel Sentinel Civic-Core cerrado de forma segura.", 
                           "\033[1;32m[●] Resguardo activo. Procesos purgados de la memoria local.\033[0m")
        sys.exit(0)

if __name__ == "__main__":
    kernel = CivicKernel()
    kernel.boot()
