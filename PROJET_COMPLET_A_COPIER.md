# 🚀 PROJET COMPLET - Formation Arabe Discord

Ce fichier contient TOUT le code de ton projet. Tu peux le copier directement sur ton PC/Raspberry Pi.

---

## 📋 TABLE DES MATIÈRES

1. [Structure du projet](#structure)
2. [Configuration](#configuration)
3. [Bot Discord](#bot-discord)
4. [Application Web](#application-web)
5. [Base de données](#base-de-données)
6. [Démarrage](#démarrage)

---

## 1️⃣ STRUCTURE DU PROJET <a name="structure"></a>

Crée cette structure de dossiers:

```
projet_finale/
├── bot/
│   ├── bot.py
│   ├── models.py
│   ├── db_connection.py
│   ├── quizzes.json
│   ├── bonus_system.py
│   ├── vote_system.py
│   ├── quiz_reviews_manager.py
│   ├── review_scheduler.py
│   ├── requirements.txt
│   └── (autres fichiers optionnels)
│
├── web/
│   ├── app.py
│   ├── models.py
│   ├── db_connection.py
│   ├── exam.json
│   ├── exercise_types.py
│   ├── requirements.txt
│   └── templates/
│       ├── exam_secure.html
│       └── exams_id.html
│
├── .env
└── README.md
```

---

## 2️⃣ CONFIGURATION <a name="configuration"></a>

### `.env` (RACINE DU PROJET)

**⚠️ NE JAMAIS PARTAGER CE FICHIER - Contient tes secrets**

```env
# Discord Bot
DISCORD_TOKEN=TON_TOKEN_DISCORD_ICI
GUILD_ID=TON_SERVEUR_ID_ICI

# Base de données PostgreSQL
DATABASE_URL=postgresql://user:password@host:port/database

# Flask (optionnel)
FLASK_ENV=production
SECRET_KEY=une_clé_secrète_aléatoire
```

**Comment obtenir ces valeurs:**

1. **DISCORD_TOKEN**: https://discord.com/developers/applications
   - Crée une application → Bot → Copy Token

2. **GUILD_ID**: Clic droit sur ton serveur Discord → Copier l'identifiant du serveur

3. **DATABASE_URL**:
   - Local: `postgresql://postgres:password@localhost:5432/formation_arabe`
   - Render/Railway: URL fournie par le service

---

## 3️⃣ BOT DISCORD <a name="bot-discord"></a>

### `bot/requirements.txt`

```txt
discord.py==2.6.4
python-dotenv==1.2.1
psycopg2-binary==2.9.9
SQLAlchemy==2.0.36
APScheduler==3.10.4
```

---

### `bot/models.py`

Télécharge le contenu depuis ton projet actuel - Le fichier est trop long pour ce document.
C'est le fichier qui définit la structure de la base de données (tables Utilisateur, Cohorte, ExamResult, etc.).

**Commande pour voir le fichier:**
```bash
cat /home/user/projet_finale/bot/models.py
```

---

### `bot/db_connection.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL manquante dans .env")

# Créer le moteur de base de données
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Créer la session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Retourne une session de base de données"""
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        raise
```

---

### `bot/quizzes.json`

```json
{
  "courses": [
    {
      "id": 1,
      "title": "Les bases de la langue arabe - Niveau 1",
      "url": "https://TON_SITE_WEB/course/1",
      "icon": "📖",
      "questions": [
        {
          "id": "arab_q1",
          "question": "En arabe, il existe plusieurs pronoms personnels. Lequel signifie 'Je' ?",
          "options": [
            "أنتَ (anta)",
            "أنا (ana)",
            "هو (huwa)",
            "نحن (nahnu)"
          ],
          "correct": 1,
          "explanation": "أنا (ana) signifie 'Je' en arabe. C'est le pronom personnel de la première personne du singulier."
        },
        {
          "id": "arab_q2",
          "question": "Comment dit-on 'Bonjour' / 'La paix soit sur vous' en arabe ?",
          "options": [
            "شكراً (choukran)",
            "مع السلامة (ma'a salama)",
            "السلام عليكم (as-salam alaykoum)",
            "صباح الخير (sabah al-khayr)"
          ],
          "correct": 2,
          "explanation": "السلام عليكم (as-salam alaykoum) signifie 'La paix soit sur vous', c'est la salutation islamique de base."
        },
        {
          "id": "arab_q3",
          "question": "Quel est le mot arabe pour 'livre' ?",
          "options": [
            "قلم (qalam) - stylo",
            "كتاب (kitab) - livre",
            "باب (bab) - porte",
            "كرسي (koursi) - chaise"
          ],
          "correct": 1,
          "explanation": "كتاب (kitab) signifie 'livre' en arabe. C'est un nom masculin très utilisé."
        },
        {
          "id": "arab_q4",
          "question": "Comment dit-on 'étudiant' au masculin en arabe ?",
          "options": [
            "طالبة (taliba)",
            "معلم (mou'allim)",
            "طالب (talib)",
            "تلميذ (tilmidh)"
          ],
          "correct": 2,
          "explanation": "طالب (talib) signifie 'étudiant' (masculin). Au féminin, on dit طالبة (taliba)."
        },
        {
          "id": "arab_q5",
          "question": "Le pronom 'هو' (huwa) signifie :",
          "options": [
            "Elle",
            "Il",
            "Nous",
            "Vous"
          ],
          "correct": 1,
          "explanation": "هو (huwa) signifie 'Il' (masculin, 3ème personne du singulier)."
        }
      ]
    }
  ]
}
```

**⚠️ Important:** Change `"url": "https://TON_SITE_WEB/course/1"` par l'URL de ton site web déployé.

---

### `bot/bot.py`

**Ce fichier est TRÈS long (1400+ lignes). Voici comment l'obtenir:**

```bash
# Copie le fichier depuis ton projet actuel
cp /home/user/projet_finale/bot/bot.py ~/bot.py
```

Ou consulte-le avec:
```bash
cat /home/user/projet_finale/bot/bot.py
```

**Fichier trop long pour être inclus ici - Récupère-le depuis ton projet actuel**

---

### `bot/vote_system.py`

**Récupère depuis ton projet:**
```bash
cat /home/user/projet_finale/bot/vote_system.py
```

---

### `bot/bonus_system.py`

**Récupère depuis ton projet:**
```bash
cat /home/user/projet_finale/bot/bonus_system.py
```

---

### `bot/quiz_reviews_manager.py`

**Récupère depuis ton projet:**
```bash
cat /home/user/projet_finale/bot/quiz_reviews_manager.py
```

---

### `bot/review_scheduler.py`

**Récupère depuis ton projet:**
```bash
cat /home/user/projet_finale/bot/review_scheduler.py
```

---

## 4️⃣ APPLICATION WEB <a name="application-web"></a>

### `web/requirements.txt`

```txt
Flask==3.0.0
Werkzeug==3.0.1
psycopg2-binary==2.9.9
SQLAlchemy==2.0.36
python-dotenv==1.2.1
gunicorn==21.2.0
requests==2.31.0
```

---

### `web/models.py`

**Copie exacte de `bot/models.py`** - Même fichier, même contenu.

---

### `web/db_connection.py`

**Copie exacte de `bot/db_connection.py`** - Même fichier, même contenu.

---

### `web/exercise_types.py`

```python
"""
Système de validation pour les différents types d'exercices
Supporte : QCM, Texte à trous, Association, Écriture libre, Ordre de mots, Traduction
"""


def normalize_arabic_text(text):
    """
    Normalise le texte arabe pour la comparaison
    - Retire les espaces en début/fin
    - Normalise les espaces multiples
    - Retire les diacritiques optionnels (tachkil)
    """
    if not text:
        return ""

    # Retirer les espaces en début/fin
    text = text.strip()

    # Normaliser les espaces multiples
    text = ' '.join(text.split())

    # Diacritiques arabes à ignorer pour la comparaison (optionnel)
    # Kasra, Fatha, Damma, Sukun, Shadda, Tanwin, etc.
    diacritics = ['\u064B', '\u064C', '\u064D', '\u064E', '\u064F',
                  '\u0650', '\u0651', '\u0652', '\u0653', '\u0654',
                  '\u0655', '\u0656', '\u0657', '\u0658', '\u0670']

    for diacritic in diacritics:
        text = text.replace(diacritic, '')

    return text


def validate_qcm(question, user_answer):
    """
    Valide une question QCM classique

    Args:
        question: dict avec 'correct' (str: "a", "b", "c", "d")
        user_answer: str ("a", "b", "c", "d")

    Returns:
        bool: True si correct
    """
    if not user_answer:
        return False

    return user_answer.lower() == question['correct'].lower()


def validate_fill_blank(question, user_answer):
    """
    Valide un exercice de texte à trous

    Args:
        question: dict avec 'correct' (int: index de la bonne réponse dans options)
        user_answer: str (index sous forme de string)

    Returns:
        bool: True si correct
    """
    if not user_answer:
        return False

    try:
        user_index = int(user_answer)
        return user_index == question['correct']
    except (ValueError, TypeError):
        return False


def validate_matching(question, user_answers):
    """
    Valide un exercice d'association

    Args:
        question: dict avec 'pairs' (list de {ar, fr})
        user_answers: dict {ar_index: fr_index}

    Returns:
        bool: True si toutes les associations sont correctes
    """
    if not user_answers or not isinstance(user_answers, dict):
        return False

    # Vérifier que toutes les paires sont correctement associées
    pairs = question['pairs']

    # Pour chaque paire, vérifier que l'utilisateur a associé le bon français
    for i, pair in enumerate(pairs):
        user_choice = user_answers.get(str(i))

        if user_choice is None:
            return False

        try:
            user_fr_index = int(user_choice)
            # Vérifier que l'index correspond à la bonne traduction
            if user_fr_index != i:
                return False
        except (ValueError, TypeError):
            return False

    return True


def validate_text_input(question, user_answer):
    """
    Valide un exercice d'écriture libre stricte

    Args:
        question: dict avec 'correct' (str) ou 'accept' (list de str)
        user_answer: str

    Returns:
        bool: True si la réponse correspond exactement (après normalisation)
    """
    if not user_answer:
        return False

    # Normaliser la réponse utilisateur
    normalized_answer = normalize_arabic_text(user_answer)

    # Vérifier si 'accept' existe (plusieurs réponses possibles)
    if 'accept' in question:
        for accepted in question['accept']:
            if normalized_answer == normalize_arabic_text(accepted):
                return True
        return False

    # Sinon, utiliser 'correct'
    return normalized_answer == normalize_arabic_text(question['correct'])


def validate_word_order(question, user_answer):
    """
    Valide un exercice d'ordre de mots

    Args:
        question: dict avec 'correct_order' (list de str)
        user_answer: str (indices séparés par des virgules, ex: "0,2,1")

    Returns:
        bool: True si l'ordre est correct
    """
    if not user_answer:
        return False

    try:
        # Parser la réponse utilisateur (indices séparés par virgules)
        user_indices = [int(x.strip()) for x in user_answer.split(',')]

        # Reconstruire la phrase avec les indices de l'utilisateur
        words_shuffled = question['words']
        user_sentence = [words_shuffled[i] for i in user_indices]

        # Comparer avec l'ordre correct
        return user_sentence == question['correct_order']
    except (ValueError, IndexError, TypeError):
        return False


def validate_translation(question, user_answer):
    """
    Valide un exercice de traduction FR → AR

    Args:
        question: dict avec 'correct_ar' (str) ou 'accept' (list de str)
        user_answer: str

    Returns:
        bool: True si la traduction est acceptée
    """
    if not user_answer:
        return False

    # Normaliser la réponse
    normalized_answer = normalize_arabic_text(user_answer)

    # Vérifier si plusieurs réponses sont acceptées
    if 'accept' in question:
        for accepted in question['accept']:
            if normalized_answer == normalize_arabic_text(accepted):
                return True
        return False

    # Sinon, utiliser 'correct_ar'
    return normalized_answer == normalize_arabic_text(question['correct_ar'])


def validate_question(question, user_answer):
    """
    Fonction principale de validation - détecte le type et valide

    Args:
        question: dict avec 'type' et données spécifiques
        user_answer: réponse de l'utilisateur (format dépend du type)

    Returns:
        bool: True si correct
    """
    question_type = question.get('type', 'qcm')

    validators = {
        'qcm': validate_qcm,
        'fill_blank': validate_fill_blank,
        'matching': validate_matching,
        'text_input': validate_text_input,
        'word_order': validate_word_order,
        'translation': validate_translation
    }

    validator = validators.get(question_type)

    if not validator:
        print(f"⚠️ Type de question inconnu: {question_type}")
        return False

    return validator(question, user_answer)
```

---

## 5️⃣ FICHIERS WEB SUITE

Fichiers trop longs pour ce document. Récupère-les avec ces commandes:

### `web/app.py`
```bash
cat /home/user/projet_finale/web/app.py > app.py
```

### `web/exam.json`
```bash
cat /home/user/projet_finale/web/exam.json > exam.json
```

### `web/templates/exam_secure.html`
```bash
cat /home/user/projet_finale/web/templates/exam_secure.html > exam_secure.html
```

### `web/templates/exams_id.html`
```bash
cat /home/user/projet_finale/web/templates/exams_id.html > exams_id.html
```

---

## 6️⃣ DÉMARRAGE <a name="démarrage"></a>

### Installation (Local / Raspberry Pi / PC)

```bash
# 1. Installer Python 3.11
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip postgresql

# 2. Cloner/Créer le projet
mkdir projet_finale
cd projet_finale

# 3. Créer l'environnement virtuel
python3.11 -m venv venv
source venv/bin/activate

# 4. Installer les dépendances BOT
cd bot
pip install -r requirements.txt
cd ..

# 5. Installer les dépendances WEB
cd web
pip install -r requirements.txt
cd ..

# 6. Configurer .env
nano .env
# Copie le contenu de la section Configuration ci-dessus

# 7. Initialiser la base de données PostgreSQL
sudo -u postgres psql
CREATE DATABASE formation_arabe;
CREATE USER formation_user WITH PASSWORD 'ton_password';
GRANT ALL PRIVILEGES ON DATABASE formation_arabe TO formation_user;
\q

# 8. Lancer le BOT
cd bot
python bot.py

# 9. Lancer le WEB (dans un autre terminal)
cd web
python app.py
```

---

## 🔥 DÉMARRAGE RAPIDE AVEC TMUX (Raspberry Pi)

```bash
# Installer tmux
sudo apt install tmux

# Créer une session
tmux new -s formation

# Fenêtre 1: Bot
cd ~/projet_finale/bot
source ../venv/bin/activate
python bot.py

# Nouvelle fenêtre (Ctrl+B puis C)
cd ~/projet_finale/web
source ../venv/bin/activate
python app.py

# Détacher la session (Ctrl+B puis D)
# Réattacher: tmux attach -t formation
```

---

## 📊 SERVICES À CRÉER (Auto-démarrage)

### Service Bot (`/etc/systemd/system/formation-bot.service`)

```ini
[Unit]
Description=Formation Arabe Discord Bot
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/projet_finale/bot
Environment="PATH=/home/pi/projet_finale/venv/bin"
ExecStart=/home/pi/projet_finale/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Service Web (`/etc/systemd/system/formation-web.service`)

```ini
[Unit]
Description=Formation Arabe Web App
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/projet_finale/web
Environment="PATH=/home/pi/projet_finale/venv/bin"
ExecStart=/home/pi/projet_finale/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Activer les services

```bash
sudo systemctl daemon-reload
sudo systemctl enable formation-bot
sudo systemctl enable formation-web
sudo systemctl start formation-bot
sudo systemctl start formation-web

# Vérifier le statut
sudo systemctl status formation-bot
sudo systemctl status formation-web

# Voir les logs
sudo journalctl -u formation-bot -f
sudo journalctl -u formation-web -f
```

---

## 🌐 ACCÈS DEPUIS INTERNET (DuckDNS + Port Forwarding)

### 1. DuckDNS (Domaine gratuit)

```bash
# Créer un compte sur https://www.duckdns.org
# Choisir un nom: ton-site.duckdns.org

# Installer le script de mise à jour
mkdir ~/duckdns
cd ~/duckdns
echo "url='https://www.duckdns.org/update?domains=TON_DOMAINE&token=TON_TOKEN&ip='" > duck.sh
chmod +x duck.sh

# Tester
./duck.sh

# Automatiser (crontab)
crontab -e
# Ajouter:
*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1
```

### 2. Port Forwarding sur ta box

- Ouvre l'interface de ta box (192.168.1.1 généralement)
- Va dans "Redirection de ports" / "Port Forwarding"
- Ajoute:
  - Port externe: 5000 → IP locale Raspberry : Port 5000 (Web)
  - Port externe: 80 → IP locale Raspberry : Port 5000 (HTTP optionnel)

### 3. Nginx (Reverse Proxy - Optionnel mais recommandé)

```bash
sudo apt install nginx

# Configuration Nginx
sudo nano /etc/nginx/sites-available/formation

# Contenu:
server {
    listen 80;
    server_name ton-domaine.duckdns.org;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Activer
sudo ln -s /etc/nginx/sites-available/formation /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔒 SÉCURITÉ

### Firewall (UFW)

```bash
sudo apt install ufw
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (si SSL)
sudo ufw enable
```

### Fail2Ban (Protection SSH)

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## ✅ VÉRIFICATION

Après installation, vérifie:

1. **Bot Discord:** Doit être en ligne sur Discord
2. **Site Web:** Accessible sur `http://localhost:5000` ou `http://ton-ip:5000`
3. **Base de données:** `sudo -u postgres psql formation_arabe`
4. **Services actifs:** `sudo systemctl status formation-bot formation-web`

---

## 🎯 CONCLUSION

Tu as maintenant:
- ✅ Bot Discord fonctionnel 24/7
- ✅ Site web accessible localement
- ✅ Base de données PostgreSQL
- ✅ Auto-démarrage au boot
- ✅ Accès depuis internet (avec DuckDNS)

**Coût:** ~9€/an d'électricité (Raspberry Pi) 🎉

---

## 📞 COMMANDES UTILES

```bash
# Redémarrer les services
sudo systemctl restart formation-bot
sudo systemctl restart formation-web

# Voir les logs en temps réel
sudo journalctl -u formation-bot -f
sudo journalctl -u formation-web -f

# Arrêter les services
sudo systemctl stop formation-bot
sudo systemctl stop formation-web

# Mettre à jour le code
cd ~/projet_finale
git pull
sudo systemctl restart formation-bot formation-web

# Sauvegarder la base de données
pg_dump -U formation_user formation_arabe > backup_$(date +%Y%m%d).sql

# Restaurer la base de données
psql -U formation_user formation_arabe < backup_20260124.sql
```

---

**🔥 Projet prêt à déployer ! Bonne chance !**
