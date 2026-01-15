# ⚙️ Configuration Render - Guide Complet

## 🎯 Deux Scénarios Possibles

Selon votre structure GitHub, les commandes changent.

---

## ✅ SCÉNARIO 1 : Avec Dossiers bot/ et web/ (RECOMMANDÉ)

### 📁 Structure GitHub :

```
votre-repo/
├── bot/
│   ├── bot.py
│   ├── requirements.txt
│   └── ...
├── web/
│   ├── app.py
│   ├── requirements.txt
│   └── templates/
└── README.md
```

### 🤖 Configuration Bot Discord

**Render Dashboard → Votre Service Bot → Settings**

| Paramètre | Valeur |
|-----------|--------|
| **Name** | `formation-bot` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r bot/requirements.txt` |
| **Start Command** | `cd bot && python bot.py` |
| **Root Directory** | *(laissez vide)* |

**Environment Variables** :
```
DATABASE_URL = postgresql://user:password@host/database
DISCORD_TOKEN = votre_token_discord
```

### 🌐 Configuration Site Web

**Render Dashboard → Votre Service Web → Settings**

| Paramètre | Valeur |
|-----------|--------|
| **Name** | `formation-web` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r web/requirements.txt` |
| **Start Command** | `cd web && gunicorn app:app` |
| **Root Directory** | *(laissez vide)* |

**Environment Variables** :
```
DATABASE_URL = postgresql://user:password@host/database
```

---

## ⚠️ SCÉNARIO 2 : Tout à la Racine (Sans Dossiers)

### 📁 Structure GitHub :

```
votre-repo/
├── bot.py
├── app.py
├── quiz.py
├── requirements.txt (??? lequel ???)
├── exams.html
└── ...
```

### 🚨 PROBLÈME : Deux requirements.txt !

Vous avez besoin de dépendances différentes pour bot et web.

#### Solution A : Créer 2 Services avec Filters

**Service Bot** :

| Paramètre | Valeur |
|-----------|--------|
| **Build Command** | `pip install discord.py==2.6.4 psycopg2-binary==2.9.9 SQLAlchemy==2.0.23 python-dotenv==1.2.1 aiohttp==3.13.3 Flask==3.0.0` |
| **Start Command** | `python bot.py` |

**Service Web** :

| Paramètre | Valeur |
|-----------|--------|
| **Build Command** | `pip install Flask==3.0.0 psycopg2-binary==2.9.9 SQLAlchemy==2.0.23 python-dotenv==1.2.1 gunicorn==21.2.0` |
| **Start Command** | `gunicorn app:app` |

#### Solution B : Renommer les Requirements

1. Sur GitHub, renommez :
   - `requirements-bot.txt` (dépendances bot)
   - `requirements-web.txt` (dépendances web)

2. Contenu `requirements-bot.txt` :
```txt
discord.py==2.6.4
Flask==3.0.0
Werkzeug==3.0.1
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
aiohttp==3.13.3
python-dotenv==1.2.1
```

3. Contenu `requirements-web.txt` :
```txt
Flask==3.0.0
Werkzeug==3.0.1
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
python-dotenv==1.2.1
gunicorn==21.2.0
```

4. Configuration Render :

**Bot** :
- Build : `pip install -r requirements-bot.txt`
- Start : `python bot.py`

**Web** :
- Build : `pip install -r requirements-web.txt`
- Start : `gunicorn app:app`

#### Solution C : Templates dans un Dossier

Si vous avez `exams.html`, `exam_take.html` à la racine :

1. Créez `templates/` sur GitHub
2. Déplacez les fichiers HTML dedans
3. Modifiez `app.py` :

```python
# Vérifiez que vous avez cette ligne
app = Flask(__name__)  # Cherchera templates/ automatiquement
```

---

## 🎯 Quelle Configuration Choisir ?

### ✅ FORTEMENT RECOMMANDÉ : Scénario 1 (Avec Dossiers)

**Pourquoi ?**
- ✅ Structure propre et professionnelle
- ✅ Séparation claire bot/web
- ✅ Facile à maintenir
- ✅ Correspond à toute la documentation
- ✅ Standards de l'industrie

**Temps pour réorganiser** : 10 minutes via GitHub interface

### ⚠️ Scénario 2 : OK mais pas idéal

**Quand l'utiliser ?**
- Vous êtes pressé
- Vous testez rapidement
- Projet temporaire

**Inconvénients** :
- Fichiers mélangés
- Confusion possible
- Maintenance difficile

---

## 🔄 Comment Passer du Scénario 2 au Scénario 1

### Via Interface GitHub (FACILE)

1. **Créer les dossiers** :
   - Add file → Create new file
   - Nom : `bot/.gitkeep`
   - Commit
   - Répéter pour `web/.gitkeep`

2. **Déplacer chaque fichier** :
   - Ouvrir le fichier
   - Cliquer sur Edit (crayon)
   - Ajouter `bot/` ou `web/` devant le nom
   - Commit

3. **Supprimer les anciens** :
   - Ouvrir chaque ancien fichier à la racine
   - Cliquer sur Delete (poubelle)
   - Commit

### Via Git (RAPIDE)

```bash
git clone https://github.com/VOTRE_USERNAME/VOTRE_REPO.git
cd VOTRE_REPO

# Créer les dossiers
mkdir -p bot web/templates

# Déplacer les fichiers BOT
git mv bot.py quiz.py scheduler.py spaced_rep.py stay_alive.py bot/
git mv cohorte_manager_sql.py database_sql.py exam_result_database_sql.py bot/
git mv db_connection.py models.py init_db.py migrate_json_to_sql.py bot/
git mv config.json bot/

# Copier pour le web
cp bot/cohorte_manager_sql.py web/
cp bot/exam_result_database_sql.py web/
cp bot/db_connection.py web/
cp bot/models.py web/

# Déplacer les fichiers WEB
git mv app.py exam.json courses_content.json web/

# Déplacer les templates
git mv *.html web/templates/

# Créer les requirements séparés
echo "discord.py==2.6.4
Flask==3.0.0
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
aiohttp==3.13.3
python-dotenv==1.2.1" > bot/requirements.txt

echo "Flask==3.0.0
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
python-dotenv==1.2.1
gunicorn==21.2.0" > web/requirements.txt

# Commit et push
git add .
git commit -m "Réorganisation : structure bot/ et web/"
git push
```

---

## 🔧 Après Réorganisation : Mettre à Jour Render

### Bot Service

1. **Dashboard** → Votre service bot → **Settings**
2. **Build & Deploy** :
   - Build Command : `pip install -r bot/requirements.txt`
   - Start Command : `cd bot && python bot.py`
3. **Manual Deploy** → **Clear build cache & deploy**

### Web Service

1. **Dashboard** → Votre service web → **Settings**
2. **Build & Deploy** :
   - Build Command : `pip install -r web/requirements.txt`
   - Start Command : `cd web && gunicorn app:app`
3. **Manual Deploy** → **Clear build cache & deploy**

---

## ✅ Vérification : Tout Fonctionne ?

### Logs Bot (doivent afficher) :

```
✅ Bot connecté en tant que BotName
✅ Serveur HTTP démarré sur port 8080
⏰ Scheduler de révisions initialisé
✅ Connexion PostgreSQL réussie
```

### Logs Web (doivent afficher) :

```
✅ Connexion PostgreSQL réussie
[INFO] Listening at: http://0.0.0.0:5000
[INFO] Using worker: sync
```

---

## 🆘 Dépannage

### Erreur "No module named 'discord'"

→ Build Command incorrect ou requirements.txt introuvable

**Solution** :
- Vérifiez le chemin : `bot/requirements.txt` existe ?
- Build Command : `pip install -r bot/requirements.txt`

### Erreur "cannot import name 'app'"

→ Start Command incorrect

**Solution** :
- Si `app.py` dans `web/` : `cd web && gunicorn app:app`
- Si `app.py` à la racine : `gunicorn app:app`

### Erreur "templates not found"

→ Flask ne trouve pas le dossier templates

**Solution** :
- Templates doivent être dans `web/templates/`
- OU à la racine dans `templates/`

### Logs "Build succeeded" mais "Deploy failed"

→ Start Command incorrect ou fichier introuvable

**Solution** :
- Vérifiez le chemin du fichier Python
- Logs Render → Regardez l'erreur exacte

---

## 📋 Checklist Configuration Render

### Bot Discord

- [ ] Build Command : `pip install -r bot/requirements.txt`
- [ ] Start Command : `cd bot && python bot.py`
- [ ] Environment : `DATABASE_URL` définie
- [ ] Environment : `DISCORD_TOKEN` définie
- [ ] Deploy réussi
- [ ] Logs affichent "Bot connecté"

### Site Web

- [ ] Build Command : `pip install -r web/requirements.txt`
- [ ] Start Command : `cd web && gunicorn app:app`
- [ ] Environment : `DATABASE_URL` définie
- [ ] Deploy réussi
- [ ] Logs affichent "Listening at"
- [ ] URL accessible dans le navigateur

---

## 🎉 Recommandation Finale

**Prenez 10 minutes pour organiser proprement avec bot/ et web/**

Ça vaut vraiment le coup :
- Code professionnel
- Facile à maintenir
- Correspond à la doc
- Évite les confusions futures

**Utilisez le guide REORGANISER_GITHUB.md pour la procédure détaillée !**

---

## 📞 Questions Fréquentes

### "Dois-je redéployer après changement des commandes ?"

Oui ! Après avoir modifié Build/Start Command :
1. **Manual Deploy** → **Clear build cache & deploy**

### "Puis-je avoir bot/ et web/ dans le même service Render ?"

Non, il faut 2 services séparés :
- 1 pour le bot
- 1 pour le web

### "Mes logs disent 'cd: no such file or directory' "

Le dossier n'existe pas. Vérifiez la structure sur GitHub.

### "Render déploie mais le bot ne répond pas"

- Vérifiez les logs : erreur ?
- Vérifiez `DISCORD_TOKEN`
- Vérifiez les intents Discord

---

**Besoin d'aide ? Consultez les logs et cherchez l'erreur exacte !**
