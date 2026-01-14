# 🚀 Guide de Déploiement Complet

## 📦 Prérequis

- Compte [Render.com](https://render.com)
- Dépôt GitHub
- PostgreSQL activé

---

## 1️⃣ Configuration PostgreSQL

### Sur Render.com :

1. Dashboard → **New PostgreSQL**
2. Nom : `formation-database`
3. Plan : Free
4. **Create Database**

5. Une fois créée, copiez l'**Internal Database URL** :
   ```
   postgresql://user:pass@host/db
   ```

---

## 2️⃣ Déploiement du Bot Discord

### A. Créer le Service

1. Dashboard → **New Web Service**
2. Connect Repository → Sélectionnez votre dépôt
3. Configuration :
   - **Name** : `formation-bot`
   - **Region** : Frankfurt (ou autre)
   - **Branch** : `main`
   - **Root Directory** : Laissez vide
   - **Runtime** : Python 3
   - **Build Command** :
     ```bash
     pip install -r bot/requirements.txt
     ```
   - **Start Command** :
     ```bash
     cd bot && python bot.py
     ```

### B. Variables d'Environnement

Ajoutez dans **Environment** :

| Clé | Valeur |
|-----|--------|
| `DATABASE_URL` | `postgresql://user:pass@host/db` |
| `DISCORD_TOKEN` | Votre token Discord |

### C. Initialiser la Base

Une fois le bot déployé, ouvrez la **Shell** dans Render :

```bash
cd bot
python init_db.py
```

✅ Cela créera toutes les tables.

---

## 3️⃣ Déploiement du Site Web

### A. Créer le Service

1. Dashboard → **New Web Service**
2. Connect Repository → Même dépôt
3. Configuration :
   - **Name** : `formation-web`
   - **Region** : Frankfurt
   - **Branch** : `main`
   - **Root Directory** : Laissez vide
   - **Runtime** : Python 3
   - **Build Command** :
     ```bash
     pip install -r web/requirements.txt
     ```
   - **Start Command** :
     ```bash
     cd web && gunicorn app:app
     ```

### B. Variables d'Environnement

Ajoutez dans **Environment** :

| Clé | Valeur |
|-----|--------|
| `DATABASE_URL` | `postgresql://user:pass@host/db` |

---

## 4️⃣ Configuration Discord

### A. Activer les Intents

1. [Discord Developer Portal](https://discord.com/developers/applications)
2. Sélectionnez votre application
3. **Bot** → **Privileged Gateway Intents** :
   - ✅ Presence Intent
   - ✅ Server Members Intent
   - ✅ Message Content Intent
4. **Save Changes**

### B. Inviter le Bot

URL d'invitation (remplacez `CLIENT_ID`) :
```
https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

---

## 5️⃣ Configuration des Examens

### Modifier exam.json

Adaptez les dates dans `/web/exam.json` :

```json
{
  "id": 1,
  "group": 1,
  "start_date": "2026-01-15T09:00:00",
  "end_date": "2026-01-30T23:59:59"
}
```

**Format** : `YYYY-MM-DDTHH:MM:SS`

---

## 6️⃣ Test du Système

### Test Bot Discord :

1. Sur votre serveur Discord :
   ```
   /send_course 1
   ```
2. Cliquez sur le bouton "Démarrer le QCM"
3. Répondez aux questions en MP

### Test Site Web :

1. Allez sur `https://formation-web.onrender.com/exams`
2. Entrez un ID Discord valide (inscrit via le bot)
3. L'examen correspondant au groupe devrait s'afficher

---

## 7️⃣ Migration des Données (si JSON existant)

Si vous avez déjà des données JSON :

1. Ouvrez la **Shell** du bot sur Render
2. Exécutez :
   ```bash
   cd bot
   python migrate_json_to_sql.py
   ```

---

## 🔍 Vérification

### Vérifier les Logs :

**Bot** :
```
✅ Bot connecté en tant que BotName
✅ Serveur HTTP démarré sur port 8080
⏰ Scheduler de révisions initialisé
```

**Web** :
```
✅ Connexion PostgreSQL réussie
 * Running on http://0.0.0.0:5000
```

### Tester la Base de Données :

Depuis la Shell :
```bash
cd bot
python
>>> from db_connection import test_connection
>>> test_connection()
✅ Connexion PostgreSQL réussie
```

---

## 🆘 Résolution de Problèmes

### Erreur "DATABASE_URL not found"

→ Vérifiez que la variable est bien ajoutée dans **Environment**

### Erreur "postgres:// not supported"

→ Le code corrige automatiquement `postgres://` → `postgresql://`

### Bot ne répond pas

1. Vérifiez les intents Discord
2. Vérifiez le token dans les variables d'environnement
3. Consultez les logs dans Render

### Site affiche "Erreur de connexion"

1. Vérifiez `DATABASE_URL`
2. Vérifiez que `init_db.py` a été exécuté
3. Testez la connexion depuis la Shell

---

## 📈 Mise à Jour

Pour déployer des modifications :

1. Push sur GitHub :
   ```bash
   git add .
   git commit -m "Update"
   git push
   ```

2. Render redéploiera automatiquement

---

## 🔒 Sécurité

- ✅ Ne commitez JAMAIS le `.env` ou les tokens
- ✅ Utilisez toujours les variables d'environnement
- ✅ Activez l'authentification à deux facteurs sur Render
- ✅ Limitez les permissions du bot Discord

---

## 📊 Monitoring

### Logs en Temps Réel :

**Render** → Service → **Logs**

### Métriques :

**Render** → Service → **Metrics**
- CPU Usage
- Memory Usage
- Request Count

---

## 💾 Backup Base de Données

### Export depuis Render :

```bash
pg_dump -h host -U user -d database > backup.sql
```

### Import :

```bash
psql -h host -U user -d database < backup.sql
```

---

## 🎉 C'est Terminé !

Votre plateforme est maintenant déployée et opérationnelle ! 🚀

- **Bot Discord** : Envoie des cours et QCM
- **Site Web** : Examens par groupe avec dates
- **PostgreSQL** : Stockage sécurisé

---

## 📞 Support

En cas de problème :
1. Consultez les logs Render
2. Vérifiez la documentation PostgreSQL
3. Testez la connexion à la base

Bon courage ! 💪
