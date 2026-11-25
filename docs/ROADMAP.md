# Sentinel Home — Roadmap & Améliorations Futures (2 IRM)

## 1. Sécurité & Accès
- **Authentification Biométrique / PIN dans l'APK** : Protéger le bouton *Unlock Door* par empreinte digitale (`local_auth` Flutter) avant tout déverrouillage à distance.
- **Clé d'API / JWT sur le Tunnel Public** : Ajouter un écran de connexion JWT (déjà prêt côté Spring Boot) devant `pc_door_server.py` pour éviter qu'une personne ayant l'URL Cloudflare ne puisse ouvrir la porte.
- **Anti-Spoof Avancé (Blink & Depth)** : Ajouter la détection de clignement des yeux (Eye Aspect Ratio) et la réflexion infrarouge pour contrer même une vidéo jouée sur un écran de téléphone.

## 2. Vidéo, Audio & Communication Bidirectionnelle
- **Interphone Vocal Bidirectionnel (WebRTC)** : Parler directement au livreur ou au visiteur depuis l'application Android vers le haut-parleur du Raspberry Pi / PC.
- **Enregistrement de Clips Courts (5–10 s MP4)** : Sauvegarder un court clip vidéo H.264 autour de chaque événement en plus du snapshot JPEG, avec purge automatique à J+30.
- **Détection de Colis dédiée (YOLOv8n / Gemini Vision)** : Alerter si un colis reste sur le paillasson pendant plus de 2 heures ou s'il disparaît sans qu'un résident connu ne soit apparu (anti-vol de colis).

## 3. Infrastructure & Déploiement Production
- **Cloudflare Named Tunnel (URL fixe gratuite)** : Lier un compte Cloudflare gratuit pour garder toujours la même URL (ex. `https://porte.mondomaine.com`) sans jamais changer l'adresse dans l'APK Android.
- **Notifications Push Natives (FCM + Telegram)** : Alerte sonore instantanée avec photo haute résolution même lorsque l'APK Android est complètement fermé en arrière-plan.
- **Mode Multi-Caméras Full-House** : Ajouter une caméra Jardin / Garage sur le même bus MQTT + tableau de bord unifié.
