# 🛡️ Sentinel Civic-Core

**Monitoreo de infraestructura anti-sabotaje que corre en un celular viejo con Termux — sin nube, sin dependencias pesadas, sin que nadie más vea tus datos.**

![version](https://img.shields.io/badge/version-2.5.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![python](https://img.shields.io/badge/python-3.9%2B-yellow)
![platform](https://img.shields.io/badge/platform-Termux%20%7C%20Linux%20%7C%20Android-lightgrey)
![CodeQL](https://github.com/contactochronoshield-cyber/Sentinel-Civil/actions/workflows/codeql.yml/badge.svg)
![Gitleaks](https://github.com/contactochronoshield-cyber/Sentinel-Civil/actions/workflows/gitleaks.yml/badge.svg)

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
- Auditoria de tunel VPN: detecta WireGuard/Tailscale, mide handshake y latencia del tunel
- Deteccion de dispositivos desconocidos en la red local (barrido de IPs, sin necesitar root), con identificacion automatica (hostname + puertos) y deteccion de dispositivos intermitentes (IoT/wearables)
- Mapa de topologia de red (Internet -> Gateway -> VPN -> LAN) con snapshot JSON para dashboard
- CPE Security Monitoring: clasifica el router en SUPPORTED / COMPENSATABLE / HIGH RISK (puertos de riesgo, DNS sospechoso)
- Clasificacion automatica del tipo de enlace WAN (fibra/4G/satelital) por latencia y jitter, con promedio movil anti-falsos-positivos
- Dual-WAN health check estilo SD-WAN (WiFi + datos moviles simultaneos)
- Deteccion de cambio de operador/SIM (anti SIM-swap)
- Dashboard web "Sentinel Command" con KPIs y tarjetas de nodo en tiempo real
- Wi-Fi Trust Monitor: detecta Evil Twin/Rogue AP si el BSSID de tu red cambia inesperadamente
- Prediccion de degradacion de enlace (regresion lineal sobre latencia, avisa antes de que se caiga del todo)
- Resumen visual del sistema en semaforo (Internet / WiFi / Seguridad / Red Local)
- Pipeline de seguridad automatico del propio proyecto: CodeQL + Gitleaks en cada push/PR
- Multi-CPE: monitorea varios routers/switches a la vez, distingue equipo comprometido de equipo caido, con recomendacion de accion
- Export a MikroTik RouterOS (--export-mikrotik): genera un .rsc con los dispositivos conocidos listo para importar
- Multi-CPE: monitorea varios routers/switches a la vez, distingue equipo comprometido de equipo caido, con recomendacion de accion
- Export a MikroTik RouterOS (--export-mikrotik): genera un .rsc con los dispositivos conocidos listo para importar

## 📸 Demo

_GIF de demostracion en vivo — proximamente._

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

## Sentinel Central Enterprise

Sentinel Central Enterprise es la capa comercial de Sentinel Civil para organizaciones que necesitan administrar múltiples nodos desde una infraestructura central propia.

**Sentinel Civil continúa siendo open source bajo licencia MIT.** Sentinel Central Enterprise añade capacidades comerciales de administración centralizada, licenciamiento, políticas, límites, auditoría y aislamiento entre organizaciones.

### Organizaciones

Diseñado para:

- ISPs y WISPs
- Empresas privadas
- Gobiernos y entidades públicas
- Universidades
- Organizaciones comunitarias
- Organizaciones sin ánimo de lucro
- Equipos que administran infraestructura distribuida

### Licenciamiento

El acceso a las capacidades Enterprise se controla mediante una licencia asociada a una organización.

Estados de licencia:

`PENDING → APPROVED → ACTIVE → SUSPENDED / EXPIRED / REVOKED`

Las licencias pueden definir:

- Organización
- Plan
- Vigencia
- Máximo de nodos
- Máximo de usuarios
- Funciones habilitadas

Una licencia suspendida, expirada o revocada no debe permitir el uso de las capacidades Enterprise correspondientes.

### Planes comerciales

#### Professional — US$1.200/año

- Hasta 100 nodos
- Hasta 10 usuarios
- Administración centralizada
- Auditoría
- Políticas organizacionales
- Soporte estándar

#### Enterprise — US$2.400/año

- Hasta 500 nodos
- Hasta 25 usuarios
- Administración multi-nodo
- Auditoría avanzada
- Políticas y límites empresariales
- Branding organizacional
- Capacidades Enterprise ampliadas

#### Government — desde US$3.600/año

- Diseñado para organizaciones públicas y despliegues de mayor escala
- 500+ nodos según configuración
- Usuarios y capacidades personalizados
- Soporte y condiciones contractuales según proyecto

Los precios son referencias comerciales y pueden variar según cantidad de nodos, usuarios, soporte, integración, despliegue y requisitos contractuales.

### Privacidad y datos

Sentinel Central está diseñado para ejecutarse en infraestructura controlada por la organización.

Los datos operativos pueden permanecer en los servidores del cliente. La licencia comercial controla el acceso a las capacidades Enterprise, pero Sentinel Central no requiere enviar continuamente los datos operativos de la organización a Chrono Shield Networks.

Cada organización posee un contexto independiente. Los recursos de una organización no deben ser administrados desde el contexto de otra organización.

### Sentinel FieldProof

Sentinel FieldProof permite generar un registro físico y digital de una intervención técnica.

Un FieldProof puede incluir:

- Identificador único
- Fecha y hora
- Nodo
- Activo intervenido
- Tipo de intervención
- Acción realizada
- Resultado
- Estado inicial y final
- Técnico
- Referencias de evidencia
- SHA-256
- Código QR
- Estado de verificación

Los registros pueden convertirse en documentos imprimibles y comprobantes físicos mediante impresoras compatibles, incluidas impresoras térmicas portátiles.

Esto permite que un técnico pueda entregar un comprobante físico después de una intervención incluso en condiciones de conectividad limitada.

### Uso legal y evidencia

FieldProof está diseñado como un mecanismo técnico de **registro, integridad y trazabilidad**.

El hash SHA-256 permite comprobar que el registro almacenado no haya sido alterado después de su generación.

**FieldProof no constituye por sí mismo una certificación legal ni garantiza la admisibilidad de una evidencia ante un tribunal.**

La validez jurídica de un registro depende de la legislación aplicable, los procedimientos de la organización, la cadena de custodia, la autenticidad de las fuentes y los requisitos de la autoridad competente.

Sentinel Civil y Sentinel Central no sustituyen asesoría jurídica, procedimientos de cumplimiento ni obligaciones regulatorias.

### Seguridad y aislamiento

Sentinel Central incorpora controles para evitar el acceso cruzado entre organizaciones.

Las operaciones sensibles pueden ejecutarse mediante un `OrganizationContext`, permitiendo comprobar que el recurso solicitado pertenece a la organización que realiza la operación.

El sistema registra eventos de auditoría relacionados con:

- Creación de organizaciones
- Creación y aprobación de licencias
- Activación y suspensión de licencias
- Accesos permitidos y denegados
- Registro de nodos
- Heartbeats y comprobaciones de salud

### Estado del módulo Enterprise

Sentinel Central Enterprise se encuentra en desarrollo activo.

Las funciones de organización, licenciamiento, políticas, límites, nodos, salud, persistencia, auditoría y aislamiento organizacional han sido sometidas a pruebas específicas.

La autenticación completa de usuarios, gestión de sesiones, MFA, firma criptográfica de licencias y otros controles necesarios para despliegues empresariales de alta seguridad continúan siendo áreas de desarrollo.

**Este módulo no debe interpretarse todavía como una plataforma de producción completamente certificada.**
