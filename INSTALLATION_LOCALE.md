# 🏠 GUIDE INSTALLATION LOCALE - Windows

## 📋 Ce dont tu as besoin

1. **Python 3.11** installé
2. **PostgreSQL** installé localement
3. **Git** (optionnel mais recommandé)
4. Ton **Token Discord** et **Server ID**

---

## 1️⃣ INSTALLER POSTGRESQL (si pas déjà fait)

### Télécharger et installer

1. Va sur: https://www.postgresql.org/download/windows/
2. Télécharge PostgreSQL (version 15 ou 16)
3. Lance l'installeur
4. **IMPORTANT:** Note le mot de passe que tu crées pour l'utilisateur `postgres`
5. Port par défaut: **5432** (garde-le)

### Créer la base de données

1. Ouvre **pgAdmin 4** (installé avec PostgreSQL)
2. Ou ouvre **CMD** et tape:
   ```cmd
   psql -U postgres
   ```
3. Entre ton mot de passe
4. Crée la base de données:
   ```sql
   CREATE DATABASE formation_arabe;
   CREATE USER formation_user WITH PASSWORD 'ton_password_ici';
   GRANT ALL PRIVILEGES ON DATABASE formation_arabe TO formation_user;
   \q
   ```

---

## 2️⃣ CONFIGURATION DU FICHIER `.env`

Crée un fichier `.env` à la RACINE du projet avec:

```env
# Discord Bot
DISCORD_TOKEN=ton_token_discord_ici
GUILD_ID=ton_server_id_ici

# Base de données LOCALE
DATABASE_URL=postgresql://formation_user:ton_password_ici@localhost:5432/formation_arabe

# Flask
FLASK_ENV=development
SECRET_KEY=dev_secret_key_local
```

**⚠️ IMPORTANT:**
- Remplace `ton_token_discord_ici` par ton vrai token Discord
- Remplace `ton_server_id_ici` par l'ID de ton serveur Discord
- Remplace `ton_password_ici` par le mot de passe PostgreSQL que tu as créé

---

## 3️⃣ STRUCTURE DU PROJET LOCAL

```
C:\Users\TonNom\Documents\projet_arabe\
├── .env                    ← CRÉER CE FICHIER
├── bot/
│   ├── bot.py
│   ├── models.py
│   ├── db_connection.py
│   ├── quizzes.json
│   ├── vote_system.py
│   ├── bonus_system.py
│   ├── quiz_reviews_manager.py
│   ├── review_scheduler.py
│   └── requirements.txt
└── web/
    ├── app.py
    ├── models.py
    ├── db_connection.py
    ├── exam.json
    ├── exercise_types.py
    ├── requirements.txt
    └── templates/
        ├── exam_secure.html
        └── exams_id.html
```

---

## 4️⃣ INSTALLER LES DÉPENDANCES

### Ouvre PowerShell ou CMD dans le dossier du projet

```cmd
cd C:\Users\TonNom\Documents\projet_arabe
```

### Crée un environnement virtuel Python

```cmd
python -m venv venv
venv\Scripts\activate
```

### Installe les dépendances BOT

```cmd
cd bot
pip install -r requirements.txt
cd ..
```

### Installe les dépendances WEB

```cmd
cd web
pip install -r requirements.txt
cd ..
```

---

## 5️⃣ MODIFIER `bot/quizzes.json` (URL locale)

Ouvre `bot/quizzes.json` et change:

```json
{
  "courses": [
    {
      "id": 1,
      "title": "Les bases de la langue arabe - Niveau 1",
      "url": "http://localhost:5000/course/1",    ← CHANGE ICI
      "icon": "📖",
      ...
    }
  ]
}
```

Remplace toutes les URLs par `http://localhost:5000/course/X`

---

## 6️⃣ INITIALISER LA BASE DE DONNÉES

### Ouvre PowerShell/CMD dans le dossier `bot/`

```cmd
cd bot
python
```

### Dans Python, tape:

```python
from models import Base
from db_connection import engine
Base.metadata.create_all(engine)
print("✅ Tables créées")
exit()
```

---

## 7️⃣ LANCER LE PROJET

### Terminal 1: Lancer le BOT

```cmd
cd C:\Users\TonNom\Documents\projet_arabe\bot
venv\Scripts\activate
python bot.py
```

Tu devrais voir:
```
✅ Connexion PostgreSQL OK
✅ Bot connecté en tant que: TonBot#1234
```

### Terminal 2: Lancer le WEB (ouvre un NOUVEAU terminal)

```cmd
cd C:\Users\TonNom\Documents\projet_arabe\web
..\venv\Scripts\activate
python app.py
```

Tu devrais voir:
```
✅ Connexion PostgreSQL OK
 * Running on http://127.0.0.1:5000
```

### Accéder au site web

Ouvre ton navigateur: **http://localhost:5000**

---

## 8️⃣ TESTER

1. **Bot Discord:** Tape `/register` sur Discord
2. **Site web:** Va sur http://localhost:5000/exams et entre ton ID Discord
3. **Base de données:** Ouvre pgAdmin pour voir les tables créées

---

## 🔧 DÉPANNAGE

### Erreur: `psycopg2` ne s'installe pas

```cmd
pip install --upgrade pip
pip install psycopg2-binary
```

### Erreur: `DATABASE_URL` not found

- Vérifie que le fichier `.env` est à la RACINE du projet
- Vérifie qu'il n'y a pas d'espaces dans les valeurs

### Erreur: Port 5432 déjà utilisé

PostgreSQL n'est pas lancé. Ouvre **Services Windows** (cherche "services") et démarre **PostgreSQL**

### Erreur: Bot ne se connecte pas

- Vérifie ton `DISCORD_TOKEN` dans `.env`
- Vérifie que le bot a bien les permissions sur ton serveur Discord

---

## 📝 FICHIERS À NE JAMAIS COMMIT SUR GITHUB

Crée un fichier `.gitignore` à la racine:

```
.env
venv/
__pycache__/
*.pyc
*.pyo
*.log
.vscode/
quiz_reviews.json
pending_questions.json
```

---

## ✅ CHECKLIST FINALE

- [ ] PostgreSQL installé et lancé
- [ ] Base de données `formation_arabe` créée
- [ ] Fichier `.env` configuré avec tes tokens
- [ ] Dépendances installées (`pip install -r requirements.txt`)
- [ ] URL dans `quizzes.json` changée en `localhost:5000`
- [ ] Tables créées dans la base de données
- [ ] Bot lancé et connecté sur Discord
- [ ] Site web accessible sur http://localhost:5000

---

## 🎯 COMMANDES RAPIDES (après installation)

### Démarrer le bot
```cmd
cd C:\...\projet_arabe\bot
venv\Scripts\activate
python bot.py
```

### Démarrer le web
```cmd
cd C:\...\projet_arabe\web
..\venv\Scripts\activate
python app.py
```

### Arrêter (dans chaque terminal)
**Ctrl + C**

---

**Tu es prêt ! 🚀**
