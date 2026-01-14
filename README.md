# 🎓 Plateforme de Formation Python - Bot Discord + Site Web

## 📋 Description

Système complet de formation avec :
- ✅ **Bot Discord** : Envoi de cours, QCM en MP, révisions espacées
- ✅ **Site Web** : Cours détaillés, examens par groupe avec dates
- ✅ **PostgreSQL** : Stockage des utilisateurs, cohortes, résultats
- ✅ **Système de groupes** : Examens filtrés par niveau

---

## 🗂️ Structure du Projet

```
projet_final/
├── bot/
│   ├── bot.py                          # Bot Discord principal
│   ├── cohorte_manager_sql.py          # Gestion des cohortes (SQL)
│   ├── database_sql.py                 # Révisions espacées (SQL)
│   ├── exam_result_database_sql.py     # Résultats examens (SQL)
│   ├── db_connection.py                # Connexion PostgreSQL
│   ├── models.py                       # Modèles SQLAlchemy
│   ├── init_db.py                      # Script d'initialisation DB
│   ├── migrate_json_to_sql.py          # Migration JSON → SQL
│   ├── quiz.py                         # Système de quiz
│   ├── scheduler.py                    # Révisions automatiques
│   ├── spaced_rep.py                   # Algorithme SM-2
│   ├── stay_alive.py                   # Keep-alive Flask
│   ├── config.json                     # Configuration cours/questions
│   └── requirements.txt                # Dépendances Python
│
├── web/
│   ├── app.py                          # Application Flask
│   ├── exam.json                       # Examens par groupe + dates
│   ├── courses_content.json            # Contenu des cours
│   ├── templates/
│   │   ├── exams.html                  # Formulaire ID Discord
│   │   ├── exam_take.html              # Interface examen
│   │   └── course_detail.html          # Page de cours
│   └── requirements.txt                # Dépendances Flask
│
└── README.md                           # Ce fichier
```

---

## 🚀 Installation et Déploiement

### 1️⃣ **Configuration PostgreSQL**

1. Créez une base PostgreSQL sur [Render.com](https://render.com)
2. Copiez l'URL de connexion (format : `postgresql://...`)
3. Ajoutez-la dans les variables d'environnement :

**Pour le Bot Discord :**
```
DATABASE_URL=postgresql://user:password@host:5432/database
DISCORD_TOKEN=votre_token_discord
```

**Pour le Site Web :**
```
DATABASE_URL=postgresql://user:password@host:5432/database
```

---

### 2️⃣ **Initialisation de la Base de Données**

```bash
# Depuis le dossier bot/
python init_db.py
```

✅ Cela créera toutes les tables nécessaires :
- `cohortes`
- `utilisateurs`
- `calendrier_examens`
- `historique_cohortes`
- `reviews`
- `exam_results`

---

### 3️⃣ **Migration des Données JSON (optionnel)**

Si vous avez déjà des données JSON :

```bash
python migrate_json_to_sql.py
```

---

### 4️⃣ **Déployer le Bot Discord**

#### Sur Render.com :

1. Créez un **Web Service**
2. Connectez votre dépôt GitHub
3. Configuration :
   - **Build Command** : `pip install -r bot/requirements.txt`
   - **Start Command** : `cd bot && python bot.py`
   - **Environment** : Python 3
4. Ajoutez les variables d'environnement :
   - `DATABASE_URL`
   - `DISCORD_TOKEN`

---

### 5️⃣ **Déployer le Site Web**

#### Sur Render.com :

1. Créez un **Web Service**
2. Connectez votre dépôt GitHub
3. Configuration :
   - **Build Command** : `pip install -r web/requirements.txt`
   - **Start Command** : `cd web && gunicorn app:app`
   - **Environment** : Python 3
4. Ajoutez la variable d'environnement :
   - `DATABASE_URL`

---

## 📖 Utilisation

### **Bot Discord**

#### Commandes Admin :

```
/send_course [numéro]           # Envoie un cours avec bouton QCM
/check_exam_results              # Vérifie et notifie les résultats web
```

#### Fonctionnement :

1. L'admin envoie `/send_course 1`
2. L'utilisateur clique sur "Démarrer le QCM"
3. Le QCM est envoyé en MP
4. Révisions automatiques programmées selon SM-2

---

### **Site Web**

#### Page d'Accueil :
- **URL** : `https://votre-site.onrender.com/`
- Bouton "Passer un examen"

#### Page Examens :
- **URL** : `https://votre-site.onrender.com/exams`
- Saisir l'ID Discord
- Le système :
  1. Vérifie si l'utilisateur existe
  2. Récupère son groupe (niveau_actuel)
  3. Filtre les examens par groupe
  4. Vérifie les dates (start_date / end_date)
  5. Affiche l'examen si disponible

---

## 🎯 Système d'Examens par Groupe

### **Exemple dans exam.json :**

```json
{
  "id": 1,
  "title": "Examen Groupe 1 - Fondamentaux Python",
  "group": 1,
  "start_date": "2026-01-15T09:00:00",
  "end_date": "2026-01-30T23:59:59",
  "passing_score": 70,
  "questions": [...]
}
```

### **Logique de Filtrage :**

1. **Utilisateur entre son ID Discord** sur `/exams`
2. **Vérification** : Existe-t-il dans `utilisateurs` ?
3. **Récupération groupe** : `niveau_actuel` de l'utilisateur
4. **Filtrage examen** : `exam.group == utilisateur.niveau_actuel`
5. **Vérification dates** : `start_date <= now <= end_date`
6. **Affichage examen** ou message d'erreur

---

## 🔧 Fichiers de Configuration

### **config.json** (Bot)

```json
{
  "channel_id": 123456789,
  "courses": [
    {
      "id": 1,
      "title": "Cours Python",
      "link": "https://site.com/course/1",
      "questions": [
        {
          "id": 1,
          "text": "Question ?",
          "choices": {"a": "...", "b": "..."},
          "correct": "a"
        }
      ]
    }
  ]
}
```

### **exam.json** (Web)

```json
{
  "exams": [
    {
      "id": 1,
      "group": 1,
      "start_date": "2026-01-15T09:00:00",
      "end_date": "2026-01-30T23:59:59",
      "questions": [...]
    }
  ]
}
```

---

## 🗃️ Base de Données

### **Tables Principales :**

#### `utilisateurs`
- `user_id` (BigInt, PK) : ID Discord
- `username` (String)
- `cohorte_id` (String, FK)
- `niveau_actuel` (Int) : **Correspond au groupe**
- `examens_reussis` (Int)
- `date_inscription` (DateTime)

#### `exam_results`
- `user_id` (BigInt, FK)
- `exam_id` (Int)
- `score` (Int)
- `percentage` (Float)
- `passed` (Boolean)
- `notified` (Boolean)
- `date` (DateTime)

---

## 🔐 Sécurité

- ✅ Variables d'environnement pour les secrets
- ✅ Validation des IDs Discord
- ✅ Vérification des dates d'examen
- ✅ Permissions administrateur sur Discord

---

## 📝 Notes Importantes

1. **Groupes = Niveaux** : Le `niveau_actuel` de l'utilisateur détermine son groupe
2. **Dates strictes** : Les examens ne sont accessibles qu'entre `start_date` et `end_date`
3. **Migration effectuée** : Vous avez déjà migré vers SQL ✅
4. **Keep-alive** : Le bot reste actif via Flask sur port 8080
5. **Notifications** : Utilisez `/check_exam_results` pour notifier les résultats web

---

## 🐛 Dépannage

### **Erreur "Utilisateur non trouvé"**
→ L'utilisateur doit d'abord s'inscrire via Discord avec `/send_course`

### **Erreur "Aucun examen disponible"**
→ Vérifiez que l'examen existe pour ce groupe dans `exam.json`

### **Erreur "L'examen n'est pas encore ouvert"**
→ Vérifiez les dates dans `exam.json` (format ISO 8601)

### **Erreur de connexion PostgreSQL**
→ Vérifiez que `DATABASE_URL` est bien définie

---

## 📚 Ressources

- [Documentation Discord.py](https://discordpy.readthedocs.io/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Render.com Docs](https://render.com/docs)

---

## 📄 Licence

Projet éducatif - Libre d'utilisation

---

## ✨ Auteur

Créé pour un système de formation progressif avec examens synchronisés.
