# 🔧 Réorganiser votre Dépôt GitHub

## 🎯 Situation Actuelle

Vous avez tous les fichiers à la racine au lieu d'avoir `bot/` et `web/`.

## ✅ Solution Simple (5 minutes)

### Méthode 1 : Via l'Interface GitHub (FACILE)

#### Étape 1 : Créer les dossiers

1. Sur GitHub, cliquez sur **"Add file"** → **"Create new file"**
2. Dans le nom du fichier, tapez : `bot/.gitkeep`
3. Cliquez sur **"Commit new file"**
4. Répétez pour `web/.gitkeep`

#### Étape 2 : Déplacer les fichiers du Bot

Pour chaque fichier du bot (bot.py, quiz.py, etc.) :

1. Ouvrez le fichier sur GitHub
2. Cliquez sur le crayon (Edit)
3. Dans le nom du fichier en haut, ajoutez `bot/` devant
   - Exemple : `bot.py` → `bot/bot.py`
4. Cliquez sur **"Commit changes"**

**Fichiers à déplacer dans bot/** :
- bot.py
- quiz.py
- scheduler.py
- spaced_rep.py
- stay_alive.py
- cohorte_manager_sql.py
- database_sql.py
- exam_result_database_sql.py
- db_connection.py
- models.py
- init_db.py
- migrate_json_to_sql.py
- config.json
- requirements.txt (celui du bot)

#### Étape 3 : Déplacer les fichiers du Web

Pour chaque fichier web :

1. Même procédure
2. Ajoutez `web/` devant
   - Exemple : `app.py` → `web/app.py`

**Fichiers à déplacer dans web/** :
- app.py
- exam.json
- courses_content.json
- cohorte_manager_sql.py (copie)
- exam_result_database_sql.py (copie)
- db_connection.py (copie)
- models.py (copie)
- requirements.txt (celui du web)

#### Étape 4 : Créer le dossier templates

1. **"Add file"** → **"Create new file"**
2. Nom : `web/templates/exams.html`
3. Copiez le contenu de votre fichier exams.html
4. **"Commit new file"**
5. Répétez pour `exam_take.html` et `course_detail.html`

#### Étape 5 : Supprimer les anciens fichiers

Pour chaque fichier déplacé à la racine :
1. Ouvrez-le
2. Cliquez sur la poubelle (Delete file)
3. **"Commit changes"**

---

### Méthode 2 : Via Git Local (SI VOUS AVEZ GIT)

```bash
# 1. Cloner votre dépôt
git clone https://github.com/VOTRE_USERNAME/VOTRE_REPO.git
cd VOTRE_REPO

# 2. Créer les dossiers
mkdir -p bot web/templates

# 3. Déplacer les fichiers BOT
mv bot.py quiz.py scheduler.py spaced_rep.py stay_alive.py bot/
mv cohorte_manager_sql.py database_sql.py exam_result_database_sql.py bot/
mv db_connection.py models.py init_db.py migrate_json_to_sql.py bot/
mv config.json bot/

# 4. Copier requirements.txt pour le bot
cp requirements.txt bot/

# 5. Déplacer les fichiers WEB
mv app.py exam.json courses_content.json web/
cp cohorte_manager_sql.py exam_result_database_sql.py db_connection.py models.py web/

# 6. Créer requirements.txt pour le web
cat > web/requirements.txt << 'EOF'
Flask==3.0.0
Werkzeug==3.0.1
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
python-dotenv==1.2.1
gunicorn==21.2.0
EOF

# 7. Déplacer les templates
mv exams.html exam_take.html course_detail.html web/templates/

# 8. Supprimer l'ancien requirements.txt à la racine
rm requirements.txt

# 9. Commit et push
git add .
git commit -m "Réorganisation : création des dossiers bot/ et web/"
git push
```

---

## ✅ Structure Finale Attendue

```
votre-repo/
├── bot/
│   ├── bot.py
│   ├── quiz.py
│   ├── scheduler.py
│   ├── spaced_rep.py
│   ├── stay_alive.py
│   ├── cohorte_manager_sql.py
│   ├── database_sql.py
│   ├── exam_result_database_sql.py
│   ├── db_connection.py
│   ├── models.py
│   ├── init_db.py
│   ├── migrate_json_to_sql.py
│   ├── config.json
│   └── requirements.txt
│
├── web/
│   ├── app.py
│   ├── exam.json
│   ├── courses_content.json
│   ├── cohorte_manager_sql.py
│   ├── exam_result_database_sql.py
│   ├── db_connection.py
│   ├── models.py
│   ├── requirements.txt
│   └── templates/
│       ├── exams.html
│       ├── exam_take.html
│       └── course_detail.html
│
├── README.md
├── INDEX.md
├── QUICKSTART.md
├── DEPLOY.md
├── CHECK.md
├── SUMMARY.md
├── CHANGES.md
├── GITHUB.md
└── .gitignore
```

---

## 🚀 Configuration Render APRÈS Réorganisation

### Pour le Bot Discord

**Service → Settings → Build & Deploy**

```
Build Command:
pip install -r bot/requirements.txt

Start Command:
cd bot && python bot.py

Root Directory:
(laissez vide)
```

### Pour le Site Web

**Service → Settings → Build & Deploy**

```
Build Command:
pip install -r web/requirements.txt

Start Command:
cd web && gunicorn app:app

Root Directory:
(laissez vide)
```

---

## ⚠️ Si Vous Ne Voulez PAS Réorganiser

Vous pouvez aussi tout laisser à la racine et adapter les commandes Render :

### Pour le Bot (sans dossiers)

```
Build Command:
pip install -r requirements.txt

Start Command:
python bot.py
```

### Pour le Site Web (sans dossiers)

**PROBLÈME** : Vous avez 2 requirements.txt différents !

**Solution** : Renommez
- `requirements-bot.txt` (pour le bot)
- `requirements-web.txt` (pour le web)

Puis :

```
Build Command (Bot):
pip install -r requirements-bot.txt

Build Command (Web):
pip install -r requirements-web.txt
```

---

## 💡 Quelle Option Choisir ?

### ✅ RECOMMANDÉ : Réorganiser avec dossiers

**Avantages** :
- Structure propre et professionnelle
- Facilite la maintenance
- Render comprend mieux la structure
- Correspond à la documentation

**Temps** : 10 minutes via GitHub ou 2 minutes via Git local

### ⚠️ Alternative : Laisser à la racine

**Avantages** :
- Plus rapide (0 minute)
- Fonctionne quand même

**Inconvénients** :
- Moins propre
- Confusion entre fichiers bot/web
- Ne correspond pas à la doc

---

## 🎯 Recommandation Finale

**Prenez 10 minutes pour réorganiser** via l'interface GitHub. C'est simple :

1. Créer `bot/` et `web/`
2. Éditer chaque fichier → Ajouter le préfixe du dossier
3. Supprimer les anciens fichiers à la racine
4. Mettre à jour Render

**Vous aurez un repo propre et professionnel !** ✨

---

## 🆘 Besoin d'aide ?

Si vous bloquez :
1. Faites des captures d'écran de votre structure actuelle
2. Je peux vous donner les commandes exactes
