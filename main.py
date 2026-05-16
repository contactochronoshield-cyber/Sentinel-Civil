cat << 'EOF' > ~/sentinel_public/main.py
import os
import sys
import time
import platform
import subprocess
from datetime import datetime

# CHRONO SHIELD NETWORKS - CIVIC CORE (PUBLIC VERSION)
TYPE = "CIVIL"
VERSION = "1.3.0-COMMUNITY"
LOG_FILE = os.path.expanduser("~/sentinel_public/sentinel_civic.log")

class CivicKernel:
    def __init__(self):
        self.running = True
        self.last_ip = None

    def log_event(self, message):
        """Escribe eventos con timestamp en el archivo de log local."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Limpiar códigos de color ANSI para el archivo de texto plano
        clean_msg = message.replace("\033[1;31m", "[ALERT] ").replace("\033[1;33m", "[WARN] ").replace("\033[32m", "").replace("\033[0m", "")
        try:
            with open(LOG_FILE, "a") as f:
                f.write(f"[{timestamp}] {clean_msg}\n")
        except Exception:
            pass

    def boot(self):
        os.system('clear')
        banner = f"[●] SENTINEL CIVIC-CORE v{VERSION} ACTIVE"
        print(f"\033[1;32m{banner}\033[0m")
        print(f"\033[1;34m[i] Archivo de log: {LOG_FILE}\033[0m")
        self.log_event("Kernel iniciado exitosamente.")
        time.sleep(1)
        
        try:
            self.monitor_loop()
        except KeyboardInterrupt:
            print("\n\033[1;31m[!] Monitoreo interrumpido por el usuario.\033[0m")
            self.shutdown()

    def monitor_loop(self):
        ciclo = 1
        while self.running:
            print(f"\n\033[1;33m--- [ CICLO DE ANÁLISIS #{ciclo} ] ---\033[0m")
            self.check_environment()
            self.check_memory()
            self.check_network()
            self.check_connectivity()
            
            print(f"\033[2m[i] Próximo análisis en 10 segundos... (Ctrl+C para salir)\033[0m")
            time.sleep(10)
            ciclo += 1

    def check_environment(self):
        try:
            print("\033[32m[+] Diagnóstico de Entorno:\033[0m")
            info = f"CPU: {platform.machine()} | SO: {platform.system()} {platform.release()}"
            print(f"  > {info}")
        except Exception as e:
            print(f"  \033[1;31m[x] Error leyendo entorno: {e}\033[0m")

    def check_memory(self):
        print("\033[32m[+] Estado de Memoria Local:\033[0m")
        if os.system("command -v free > /dev/null 2>&1") == 0:
            os.system("free -m | grep -E 'Mem|Total'")
        else:
            print("  \033[1;33m[!] Alerta: Comando 'free' no disponible.\033[0m")

    def check_network(self):
        print("\033[32m[+] Interfaces de Red Activas:\033[0m")
        if os.system("command -v ip > /dev/null 2>&1") == 0:
            # Obtener la IP actual de forma limpia para rastrear cambios
            try:
                cmd = "ip -4 addr show | grep -E 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | head -n 1"
                current_ip = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
                
                if current_ip:
                    print(f"  > IP Detectada: {current_ip}")
                    if self.last_ip and self.last_ip != current_ip:
                        msg = f"\033[1;31m[ALERTA COLECTIVA] ¡La dirección IP cambió! Antigua: {self.last_ip} -> Nueva: {current_ip}\033[0m"
                        print(f"  {msg}")
                        self.log_event(msg)
                    self.last_ip = current_ip
                else:
                    print("  > No se detectaron IPs públicas/locales activas.")
            except Exception:
                os.system("ip -4 addr show | grep -E 'inet |wlan0|rmnet'")
        else:
            print("  \033[1;33m[!] Alerta: Comando 'ip' no disponible.\033[0m")

    def check_connectivity(self):
        print("\033[32m[+] Verificación de Enlace Seguro (Ping a Cloudflare):\033[0m")
        # En Android/Termux el parámetro para contar pings es -c
        param = "-c 1" if platform.system().lower() != "windows" else "-n 1"
        timeout = "-W 2" if platform.system().lower() != "windows" else "-w 2000"
        
        response = os.system(f"ping {param} {timeout} 1.1.1.1 > /dev/null 2>&1")
        if response == 0:
            print("  > \033[1;32m[OK] Conectividad WAN íntegra. Enlace activo.\033[0m")
        else:
            msg = "\033[1;33m[ALERTA] Pérdida de conectividad WAN o interfaz bloqueada.\033[0m"
            print(f"  {msg}")
            self.log_event(msg)

    def shutdown(self):
        self.running = False
        self.log_event("Kernel cerrado por el usuario de forma segura.")
        print("\033[1;32m[●] Sentinel Civic-Core se ha cerrado de forma segura. Resguardo activo.\033[0m")
        sys.exit(0)

if __name__ == "__main__":
    kernel = CivicKernel()
    kernel.boot()
EOF
