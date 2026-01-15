# 🆘 Dépannage - Erreurs Courantes

## 🐛 Erreur SQLAlchemy + Python 3.13

### Symptôme

```
AssertionError: Class <class 'sqlalchemy.sql.elements.SQLCoreOperations'> 
directly inherits TypingOnly but has additional attributes
```

### Cause

**SQLAlchemy 2.0.23** n'est **pas compatible** avec **Python 3.13**

### ✅ Solution (2 options)

#### Option A : Forcer Python 3.11 (RECOMMANDÉ)

1. **Ajoutez ces fichiers à la racine de votre dépôt GitHub** :

**`.python-version`** :
```
3.11.0
```

**`runtime.txt`** :
```
python-3.11.0
```

2. **Commitez et poussez** :
```bash
git add .python-version runtime.txt
git commit -m "Force Python 3.11 pour compatibilité SQLAlchemy"
git push
```

3. **Sur Render** :
   - **Manual Deploy** → **Clear build cache & deploy**

#### Option B : Mettre à jour SQLAlchemy

**Modifiez `bot/requirements.txt`** :
```txt
SQLAlchemy==2.0.36  # Au lieu de 2.0.23
```

**Modifiez `web/requirements.txt`** :
```txt
SQLAlchemy==2.0.36  # Au lieu de 2.0.23
```

Puis :
```bash
git add bot/requirements.txt web/requirements.txt
git commit -m "Update SQLAlchemy to 2.0.36 for Python 3.13"
git push
```

---

## 🔌 Erreur "No module named 'discord'"

### Symptôme

```
ModuleNotFoundError: No module named 'discord'
```

### Cause

Le fichier `requirements.txt` n'est pas trouvé ou le Build Command est incorrect.

### ✅ Solution

**Render → Settings → Build & Deploy**

Vérifiez :
```
Build Command: pip install -r bot/requirements.txt
```

Si tout est à la racine (pas de dossier bot/) :
```
Build Command: pip install -r requirements.txt
```

---

## 🗄️ Erreur "could not connect to server"

### Symptôme

```
OperationalError: could not connect to server: Connection refused
```

### Cause

`DATABASE_URL` incorrecte ou PostgreSQL non accessible.

### ✅ Solution

1. **Vérifier DATABASE_URL** :
   - Render → Service → Environment
   - Format : `postgresql://user:pass@host:5432/db`

2. **Vérifier que PostgreSQL est créé** :
   - Render Dashboard → Databases
   - Doit être "Available"

3. **Tester la connexion** :
   ```bash
   # Dans Render Shell
   python -c "from db_connection import test_connection; test_connection()"
   ```

---

## 🔑 Erreur "Privileged intent provided is not enabled"

### Symptôme

```
discord.errors.PrivilegedIntentsRequired: Shard ID None is requesting 
privileged intents that have not been explicitly enabled
```

### Cause

Les intents Discord ne sont pas activés.

### ✅ Solution

1. [Discord Developer Portal](https://discord.com/developers/applications)
2. Votre application → **Bot**
3. **Privileged Gateway Intents** :
   - ✅ **Presence Intent**
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
4. **Save Changes**
5. Redémarrez le bot sur Render

---

## 📁 Erreur "No such file or directory"

### Symptôme

```
cd: bot: No such file or directory
```

### Cause

La structure GitHub ne correspond pas aux commandes Render.

### ✅ Solution

**2 cas possibles** :

#### Cas 1 : Vous AVEZ les dossiers bot/ et web/

**Vérifiez sur GitHub** : Les dossiers existent ?

**Start Command doit être** :
```
cd bot && python bot.py
```

#### Cas 2 : TOUT est à la racine

**Pas de dossier bot/, web/** → Les fichiers sont mélangés à la racine

**Start Command doit être** :
```
python bot.py
```

**Build Command** :
```
pip install discord.py==2.6.4 Flask==3.0.0 psycopg2-binary==2.9.9 SQLAlchemy==2.0.36 python-dotenv==1.2.1 aiohttp==3.13.3
```

---

## 🌐 Erreur "TemplateNotFound: exams.html"

### Symptôme

```
jinja2.exceptions.TemplateNotFound: exams.html
```

### Cause

Flask ne trouve pas le dossier `templates/`.

### ✅ Solution

**Vérifiez la structure** :

#### Si structure avec dossiers :
```
web/
├── app.py
└── templates/
    ├── exams.html
    ├── exam_take.html
    └── course_detail.html
```

#### Si tout à la racine :
```
/
├── app.py
└── templates/
    ├── exams.html
    ├── exam_take.html
    └── course_detail.html
```

**Flask cherche automatiquement dans `templates/` au même niveau que `app.py`**

---

## 🔐 Erreur "authentication failed"

### Symptôme

```
FATAL: password authentication failed for user
```

### Cause

`DATABASE_URL` incorrecte ou expirée.

### ✅ Solution

1. **Render Dashboard** → **PostgreSQL Database**
2. **Connection** → Copiez **Internal Database URL**
3. **Service Bot** → **Environment** → Mettez à jour `DATABASE_URL`
4. **Service Web** → **Environment** → Mettez à jour `DATABASE_URL`
5. **Redéployez les 2 services**

---

## ⏱️ Erreur "Health check timeout"

### Symptôme

```
Your service is not responding to HTTP requests at /
```

### Cause

Le service ne démarre pas assez vite ou crash au démarrage.

### ✅ Solution

1. **Consultez les logs** :
   - Y a-t-il une erreur Python ?
   - Le bot se connecte-t-il ?

2. **Pour le bot** :
   - Vérifiez que `stay_alive.py` lance bien Flask sur port 8080
   - Logs doivent afficher : "Serveur HTTP démarré sur port 8080"

3. **Pour le web** :
   - Gunicorn doit démarrer sur port 5000
   - Logs : "Listening at: http://0.0.0.0:5000"

---

## 🔄 Erreur "Build failed"

### Symptôme

Le build échoue avant même de lancer le Start Command.

### ✅ Solution

1. **Consultez les logs de build** :
   - Quelle ligne échoue ?

2. **Erreurs communes** :
   - `requirements.txt` introuvable → Vérifiez le chemin dans Build Command
   - Dépendance incompatible → Mettez à jour les versions
   - Python version incompatible → Ajoutez `runtime.txt`

---

## 📊 Checklist Débogage Générale

### Pour le Bot

- [ ] `DISCORD_TOKEN` défini dans Environment
- [ ] `DATABASE_URL` défini dans Environment
- [ ] Build Command : `pip install -r bot/requirements.txt` (ou sans `bot/`)
- [ ] Start Command : `cd bot && python bot.py` (ou `python bot.py`)
- [ ] Intents Discord activés
- [ ] Python 3.11 forcé (`.python-version` et `runtime.txt`)

### Pour le Web

- [ ] `DATABASE_URL` défini dans Environment
- [ ] Build Command : `pip install -r web/requirements.txt` (ou sans `web/`)
- [ ] Start Command : `cd web && gunicorn app:app` (ou `gunicorn app:app`)
- [ ] `templates/` au bon endroit
- [ ] Python 3.11 forcé

---

## 🔍 Comment Lire les Logs Render

### Logs de Build (pendant `pip install`)

```
==> Building...
Step 1/5 : pip install -r bot/requirements.txt
...
Successfully installed discord.py-2.6.4 ...
==> Build completed
```

✅ Si succès : Passez au Start Command  
❌ Si erreur : Vérifiez requirements.txt

### Logs de Start (pendant l'exécution)

```
==> Running 'cd bot && python bot.py'
✅ Connexion PostgreSQL réussie
✅ Bot connecté en tant que BotName
✅ Serveur HTTP démarré sur port 8080
```

✅ Si ces messages apparaissent : **Tout fonctionne !**  
❌ Si erreur ou crash : **Lisez le message d'erreur**

---

## 🆘 Toujours Bloqué ?

### Informations à Fournir

1. **Logs complets** (Build + Start)
2. **Capture d'écran** de votre structure GitHub
3. **Commandes Render** (Build & Start)
4. **Message d'erreur exact**

### Ressources

- [Render Docs](https://render.com/docs)
- [Discord.py Docs](https://discordpy.readthedocs.io/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)

---

## 📋 Résumé Solutions Rapides

| Problème | Solution Rapide |
|----------|----------------|
| SQLAlchemy + Python 3.13 | Ajouter `runtime.txt` avec `python-3.11.0` |
| No module named 'discord' | Vérifier Build Command |
| No such file or directory | Adapter Start Command à structure GitHub |
| Templates not found | Vérifier `templates/` au même niveau que `app.py` |
| PostgreSQL connection | Vérifier `DATABASE_URL` |
| Discord intents | Activer dans Developer Portal |

---

**La plupart des erreurs viennent de :**
1. ❌ Mauvais chemin dans Build/Start Command
2. ❌ Variables d'environnement manquantes
3. ❌ Incompatibilité de versions (Python/SQLAlchemy)

**Vérifiez ces 3 points en premier !** ✅
