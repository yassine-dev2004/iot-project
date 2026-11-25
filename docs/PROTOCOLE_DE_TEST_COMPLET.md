# GUIDE DE TEST COMPLET & EXCELLENCE POUR SOUTENANCE 2 IRM
**Projet : Smart Door Camera (Raspberry Pi Edge + Backend Spring Boot + IoT Node ESP32 + 3D Simulation)**  
**Auteur : Yassine Mezghanni**

---

## 1. Vue d'Ensemble des Améliorations Apportées

Le système a été poussé à son niveau maximal d'ingénierie :
1. **Simulation 3D & Digital Twin Photoréaliste ([sim/index.html](file:///c:/Users/yassine%20mezghanni/Desktop/2%20IRM/iot%20projet%20last%20one/sim/index.html))** :
   - Porte en chêne avec pivot charnière et **ouverture motorisée physique animée à 80° en temps réel**.
   - Cône FOV caméra semi-transparent haute précision.
   - Éclairage multi-sources avec applique murale et **mode Jour/Nuit dynamique**.
   - **Acteurs 3D complets** : Personne autorisée (Alice), Inconnu/Rôdeur, Livreur avec casquette et dépôt d'un colis 3D sur le paillasson.
   - **Mockup Smartphone interactif** avec flux temps réel et widget de verrou motorisé dynamique.
2. **Actionnement Cyber-Physique Conforme** :
   - Déverrouillage automatique de la porte pendant 10 secondes si la personne est reconnue.
   - Déclenchement alarme (LED rouge + Buzzer) si la personne est un inconnu rôdant.
   - Gestion de l'anti-spoofing (liveness) empêchant l'usage d'une simple photo.
   - Filtre IA `IGNORE` si aucun événement utile n'a lieu.

---

## 2. Protocole de Test Étape par Étape (Full Demo)

### Test 1 : Le Jumeau Numérique 3D & Pipeline en Direct
1. Ouvrez dans votre navigateur : [sim/index.html](file:///c:/Users/yassine%20mezghanni/Desktop/2%20IRM/iot%20projet%20last%20one/sim/index.html)
2. **Ce qu'il faut tester devant le jury / évaluateur** :
   - **Action 1 : Cliquez sur « 👤 Personne Connue »** :
     - *Ce qui se passe :* Le personnage vert (Alice) apparaît sous le cône de la caméra.
     - *Résultat IA :* Détection YuNet + Matching SFace local validé (Score cosinus 0.82).
     - *Résultat Actionneur :* **La porte en bois pivote et s'ouvre physiquement à 80°**, la LED de serrure passe au vert, et le smartphone reçoit : *« Alice est arrivée. La porte s'ouvre automatiquement. »*.
     - *Après 10 secondes :* La porte se referme automatiquement et la LED redevient rouge.
   - **Action 2 : Cliquez sur « 🚨 Visiteur Inconnu »** :
     - *Ce qui se passe :* Le personnage rouge apparaît.
     - *Résultat IA :* Aucune correspondance dans la base locale d'embeddings.
     - *Résultat Actionneur :* **La porte reste strictement verrouillée**, l'alarme se déclenche, et le smartphone reçoit une alerte intrusion rouge.
   - **Action 3 : Cliquez sur « 📦 Livreur & Colis »** :
     - *Ce qui se passe :* Le livreur bleu dépose un carton 3D sur le paillasson.
     - *Résultat IA :* Légende Gemini : *« Colis déposé sur le pas de porte »*, mise à jour de l'écran OLED.
   - **Action 4 : Cliquez sur « ☀️ / 🌙 Basculer Jour / Nuit »** pour démontrer l'adaptabilité de la caméra dans l'obscurité.
   - **Action 5 : Faites tourner la caméra avec la souris** pour explorer la scène 3D sous tous les angles.

---

### Test 2 : Validation de la Vision Edge & Tests Unitaires (Terminal)
Dans un terminal ou via le script `tester_projet.bat` :
1. **Lancer les tests unitaires :**
   ```bash
   python -m pytest edge/tests -v
   ```
   *Résultat attendu : 100% des tests validés (`4 passed`).*

2. **Tester l'enrôlement facial sans fuite de données :**
   ```bash
   python -m edge.main enroll --name "Alice" --source video.mp4
   ```
   *Résultat : L'embedding est calculé localement via YuNet/SFace et inséré dans SQLite sans jamais être transmis au cloud.*

3. **Lancer la boucle de surveillance continue :**
   ```bash
   python -m edge.main run --source video.mp4
   ```

---

### Test 3 : Tableau de Bord Web SSE & Backend
1. Démarrez l'infrastructure (Docker) :
   ```bash
   docker compose up -d
   ```
2. Ouvrez [web/index.html](file:///c:/Users/yassine%20mezghanni/Desktop/2%20IRM/iot%20projet%20last%20one/web/index.html) pour voir le flux en direct Server-Sent Events (SSE) et les statistiques du jour générées par Gemini.
3. Injectez des faux événements pour tester le flux :
   ```bash
   python seed_events.py
   ```
