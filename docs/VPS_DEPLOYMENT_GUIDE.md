# Guide de Déploiement sur VPS (Virtual Private Server)

Ce guide détaille comment déployer le backend central, la base de données PostgreSQL, le broker MQTT et le tableau de bord web sur un VPS (Debian, Ubuntu, Ubuntu Server, etc.).

---

## 1. Pourquoi déployer sur un VPS ?

1. **Accessibilité Globale 24/7** : Le Raspberry Pi à la maison et l'application mobile en déplacement peuvent joindre le serveur à tout moment sans ouvrir de ports sur votre box internet personnelle.
2. **IP Publique & Nom de Domaine** : Permet de configurer HTTPS/SSL gratuitement avec Let's Encrypt / Nginx pour sécuriser les flux SSE et les téléversements.
3. **Persistance des Données** : Les enregistrements d'événements et les instantanés JPEG restent en lieu sûr même si le Raspberry Pi est volé ou déconnecté.

---

## 2. Déploiement en 1 Clic (Script Automatique)

Transférez le dossier du projet sur votre VPS via `scp` ou `git clone`, puis exécutez le script d'installation :

```bash
chmod +x deploy_vps.sh
./deploy_vps.sh
```

Ce script :
1. Installe Docker et Docker Compose automatiquement si nécessaire.
2. Lance les 3 conteneurs clés :
   - **PostgreSQL 16** (port `5432`)
   - **Eclipse Mosquitto MQTT** (port `1883`)
   - **Spring Boot 3 Backend** (port `8080`)

---

## 3. Configuration des Ports sur le Pare-Feu du VPS (UFW / Cloud Provider)

Assurez-vous que les ports suivants sont ouverts :

| Port | Protocole | Service | Rôle |
|---|---|---|---|
| **8080** (ou 80/443 avec Nginx) | TCP | Spring Boot REST / SSE | Ingestion des snapshots et flux live pour mobile/web |
| **1883** | TCP | Mosquitto MQTT | Communication entre le Raspberry Pi et l'ESP32 |

Exemple avec UFW sur Ubuntu :
```bash
sudo ufw allow 8080/tcp
sudo ufw allow 1883/tcp
sudo ufw reload
```

---

## 4. Configuration des Clients pour pointer vers le VPS

### Côté Raspberry Pi (`/edge/.env`) :
Remplacez l'adresse locale par l'adresse IP publique de votre VPS :
```bash
BACKEND_URL=http://<IP_DU_VPS>:8080/api/events
```

### Côté ESP32 / Nœud IoT (`iot/src/main.cpp`) :
```cpp
const char* MQTT_BROKER = "<IP_DU_VPS>";
const int MQTT_PORT = 1883;
```

### Côté Application Mobile Flutter (`mobile/lib/main.dart`) :
Réglez l'URL de base sur :
```dart
final String backendUrl = "http://<IP_DU_VPS>:8080";
```
