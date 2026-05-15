import os, sys, time, platform

# CHRONO SHIELD NETWORKS - CIVIC CORE (PUBLIC VERSION)
TYPE = "CIVIL"
VERSION = "1.2.0-COMMUNITY"

class CivicKernel:
    def boot(self):
        print(f"\n\033[1;32m[●] SENTINEL CIVIC-CORE v{VERSION} ACTIVE\033[0m")
        print("ORGANIZACIÓN: CHRONO SHIELD NETWORKS | ENTORNO PÚBLICO")
        print("-" * 50)
        self.monitor_system()

    def monitor_system(self):
        print("\n\033[32m[i] Ejecutando análisis de entorno local...\033[0m")
        time.sleep(0.5)
        
        # Datos del Sistema
        print(f" > Arquitectura de CPU: {platform.machine()}")
        print(f" > Sistema Operativo: {platform.system()} {platform.release()}")
        
        # Telemetría de Memoria
        print("\n > Estado de la memoria física:")
        os.system("free -m | grep -E 'Mem|Total'")
        
        # Telemetría de Red Básica
        print("\n > Estado de interfaces de red activas:")
        os.system("ip -4 addr show | grep -E 'inet|wlan0|rmnet'")
        
        print(f"\n\033[32m[OK] Diagnóstico finalizado con éxito.\033[0m")

if __name__ == "__main__":
    CivicKernel().boot()
