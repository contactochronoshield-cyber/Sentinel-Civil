# 🛡️ Sentinel Civic-Core

**Monitoreo de infraestructura anti-sabotaje que corre en un celular viejo con Termux — sin nube, sin dependencias pesadas, sin que nadie más vea tus datos.**

![version](https://img.shields.io/badge/version-1.7.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![python](https://img.shields.io/badge/python-3.9%2B-yellow)
![platform](https://img.shields.io/badge/platform-Termux%20%7C%20Linux%20%7C%20Android-lightgrey)

---

## ¿Por qué existe esto?

En Latinoamérica, la infraestructura crítica (redes mesh, nodos comunitarios, enlaces WISP) suele depender de dispositivos baratos, conexiones inestables, y cero visibilidad cuando algo se manipula o se cae. Las soluciones de monitoreo "serias" asumen que tenés un datacenter, no un teléfono Android reciclado corriendo Termux en una azotea.

**Sentinel Civic-Core** nació de esa necesidad real: un kernel de monitoreo liviano, sin dependencias de nube, que corre en cualquier cosa con Python 3 — y que avisa **al instante** si alguien toca una interfaz de red, si cae el enlace WAN, o si un recurso se dispara.

Es la pieza base de código abierto detrás de la infraestructura de [Chrono Shield Networks](https://github.com/contactochronoshield-cyber).

## ✨ Qué hace

- 🔍 **Anti-tamper de red** — detecta cambios de IP en tus interfaces críticas (WiFi, datos móviles) en tiempo real
- 📡 **Telemetría WAN activa** — mide latencia y packet loss contra un target configurable, sin esperar a que el usuario reporte "no hay internet"
- 💾 **Persistencia real** — todo queda en SQLite, consultable, no solo en un `.log` que nadie relee
- 🔔 **Alertas por Telegram** — te enterás en el celular al momento, no revisando logs a mano
- 🌐 **Multi-nodo centralizado** — varios dispositivos reportando a un solo dashboard, ideal para redes mesh distribuidas
- ⚙️ **Config externo** — sin tocar código: intervalos, interfaces, umbrales, todo en `config.json`
- 🪶 **Cero dependencias pesadas** — corre en un teléfono Android de gama baja con Termux, sin GPU, sin Docker, sin nube
- Alerta temprana de degradacion de senal RSSI, ideal para WISPs con antenas
- Modo Site Survey (--survey) para encontrar el mejor punto de senal en un edificio

## 🚀 Quickstart

```bash
git clone https://github.com/contactochronoshield-cyber/Sentinel-Civil.git
cd Sentinel-Civil
python3 main.py
```

Al primer arranque se genera `~/sentinel_public/config.json` con valores por defecto. Editalo para activar Telegram o reporte centralizado, y volvé a correr. Eso es todo.

## 🏗️ Arquitectura

```
┌─────────────────┐        ┌─────────────────┐
│   Nodo A         │        │   Nodo B         │
│  (main.py)       │        │  (main.py)       │
│  SQLite local     │        │  SQLite local     │
└───────┬─────────┘        └─────────┬─────────┘
         │   POST /api/sentinel/report        │
         └───────────────┬─────────────────────┘
                          ▼
              ┌───────────────────────┐
              │  Servidor central       │
              │  (Flask + SQLite)       │
              │  /api/sentinel/nodes    │
              └───────────────────────┘
                          │
                          ▼
                 Dashboard / Telegram
```

Cada nodo corre de forma completamente autónoma (guarda todo localmente aunque el servidor central esté caído) y opcionalmente reporta su estado a un punto central para visión unificada de toda la red.

## 📱 ¿Buscás esto con interfaz gráfica?

Este repo es el **kernel core**, pensado para terminal y automatización. Si preferís una app Android con interfaz visual, notificaciones nativas y panel de control táctil, mirá **Chrono Sentinel** (próximamente en Google Play) — construida sobre esta misma filosofía de soberanía y monitoreo anti-sabotaje.

## 🗺️ Roadmap

- [ ] Detección de caída de servicios/procesos críticos
- [ ] Alertas por umbral configurable de CPU/RAM sostenido
- [ ] Modo daemon persistente (`termux-services`)
- [ ] Dashboard web ligero para el servidor central
- [ ] Soporte para más canales de notificación (ntfy.sh, webhook genérico)

## 🤝 Contribuir

Este proyecto es de código abierto porque creemos que el monitoreo de infraestructura crítica no debería depender de una sola empresa. PRs, issues y forks son bienvenidos.

## 📄 Licencia

MIT — usalo, modificalo, deployalo donde quieras.

---

<sub>Desarrollado por Chrono Shield Networks — infraestructura digital soberana para Latinoamérica.</sub>
