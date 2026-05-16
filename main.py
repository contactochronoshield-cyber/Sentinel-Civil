import os
import sys
import time
import platform

# CHRONO SHIELD NETWORKS - CIVIC CORE (PUBLIC VERSION)
TYPE = "CIVIL"
VERSION = "1.2.5-COMMUNITY"

class CivicKernel:
    def __init__(self):
        self.running = True

    def boot(self):
        # Limpiar pantalla inicial
        os.system('clear')
        print(f"\033[1;32m[●] SENTINEL CIVIC-CORE v{VERSION} ACTIVE\033[0m")
        print(f"\033[1;34m[i] Inicializando infraestructura modular pública...\033[0m")
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
            
            print(f"\033[2m[i] Próximo análisis en 10 segundos... (Ctrl+C para salir)\033[0m")
            time.sleep(10)
            ciclo += 1

    def check_environment(self):
        try:
            print("\033[32m[+] Diagnóstico de Entorno:\033[0m")
            print(f"  > Arquitectura CPU : {platform.machine()}")
            print(f"  > Sistema Operativo: {platform.system()} {platform.release()}")
        except Exception as e:
            print(f"  \033[1;31m[x] Error leyendo entorno: {e}\033[0m")

    def check_memory(self):
        print("\033[32m[+] Estado de Memoria Local:\033[0m")
        # Validar si el comando free está disponible en el entorno
        if os.system("command -v free > /dev/null 2>&1") == 0:
            os.system("free -m | grep -E 'Mem|Total'")
        else:
            print("  \033[1;33m[!] Alerta: Comando 'free' no disponible en este subsistema.\033[0m")

    def check_network(self):
        print("\033[32m[+] Interfaces de Red Activas:\033[0m")
        # Validar si el comando ip está disponible
        if os.system("command -v ip > /dev/null 2>&1") == 0:
            # Captura y filtra interfaces críticas como wlan0 o rmnet de telefonía
            os.system("ip -4 addr show | grep -E 'inet |wlan0|rmnet'")
        else:
            print("  \033[1;33m[!] Alerta: Comando 'ip' no disponible. Verifique privilegios en Termux.\033[0m")

    def shutdown(self):
        self.running = False
        print("\033[1;32m[●] Sentinel Civic-Core se ha cerrado de forma segura. Resguardo activo.\033[0m")
        sys.exit(0)

if __name__ == "__main__":
    kernel = CivicKernel()
    kernel.boot()
