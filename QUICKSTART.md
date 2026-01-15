# ⚡ Démarrage Rapide - 5 Minutes

## 🎯 Objectif

Déployer le système complet en moins de 5 minutes.

---

## 📋 Checklist Rapide

- [ ] Compte Render.com créé
- [ ] Dépôt GitHub créé
- [ ] Token Discord obtenu

---

## 🚀 Étape 1 : PostgreSQL (1 min)

### Render.com

1. **Dashboard** → **New PostgreSQL**
2. Nom : `formation-db`
3. **Create Database**
4. Copier **Internal Database URL**

```
postgresql://user:XXX@host/db
```

---

## 🤖 Étape 2 : Bot Discord (2 min)

### A. Déployer

1. **Dashboard** → **New Web Service**
2. Connect GitHub → Votre dépôt
3. **Build** : `pip install -r bot/requirements.txt`
4. **Start** : `cd bot && python bot.py`
5. **Environment** :
   ```
   DATABASE_URL = postgresql://...
   DISCORD_TOKEN = votre_token
   ```
6. **Create Web Service**

### B. Initialiser

Une fois déployé, ouvrir **Shell** :

```bash
cd bot
python init_db.py
```

---

## 🌐 Étape 3 : Site Web (2 min)

### Déployer

1. **Dashboard** → **New Web Service**
2. Connect GitHub → Même dépôt
3. **Build** : `pip install -r web/requirements.txt`
4. **Start** : `cd web && gunicorn app:app`
5. **Environment** :
   ```
   DATABASE_URL = postgresql://...
   ```
6. **Create Web Service**

---

## 🎮 Étape 4 : Discord (30 sec)

### Activer Intents

[Developer Portal](https://discord.com/developers/applications)
→ Bot → **Privileged Gateway Intents** :
- ✅ Message Content
- ✅ Server Members
- ✅ Presence

### Inviter Bot

```
https://discord.com/api/oauth2/authorize?client_id=VOTRE_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

---

## ✅ Test (30 sec)

### Discord

```
/send_course 1
```

→ Cliquez sur le bouton
→ Répondez au QCM

### Site Web

```
https://votre-web.onrender.com/exams
```

→ Entrez votre ID Discord
→ Passez l'examen

---

## 🎉 C'est Fini !

Votre système est opérationnel ! 🚀

### Prochaines Étapes

1. Configurez les dates dans `web/exam.json`
2. Ajoutez vos cours dans `web/courses_content.json`
3. Consultez `CHECK.md` pour vérifier tout fonctionne

---

## 🆘 Problème ?

### Bot ne démarre pas

→ Vérifiez `DATABASE_URL` et `DISCORD_TOKEN`

### Web ne démarre pas

→ Vérifiez `DATABASE_URL`

### Tables manquantes

→ Relancez `python init_db.py` dans la Shell

---

## 📚 Documentation Complète

- **README.md** : Documentation détaillée
- **DEPLOY.md** : Guide complet déploiement
- **CHECK.md** : Vérification système
- **SUMMARY.md** : Résumé technique

---

**Temps total : ~5 minutes** ⏱️
