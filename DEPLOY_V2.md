# 🚀 Déploiement Version 2.0 - Système Complet

## 🎯 Nouvelles Fonctionnalités

Cette version ajoute :
- ✅ **Onboarding automatique** : Rôles et salons créés automatiquement
- ✅ **Gestion dynamique des groupes** : 15 membres max par sous-groupe (1-A, 1-B, etc.)
- ✅ **Promotion automatique** : Passage au niveau supérieur après réussite d'examen
- ✅ **3 salons par groupe** : Ressources, Entraide, Vocal
- ✅ **Suppression /send_course** : Système simplifié

---

## 📦 Nouveaux Fichiers

```
bot/
├── onboarding.py          ← NOUVEAU : Gestion onboarding automatique
├── promotion.py           ← NOUVEAU : Gestion promotions
├── bot_new.py             ← NOUVEAU : Bot principal v2.0
├── add_groupe_column.py   ← NOUVEAU : Migration DB
├── models.py              ← MODIFIÉ : Ajout colonne 'groupe'
└── ...
```

---

## 🔄 ÉTAPE 1 : Mise à Jour GitHub

### Sur GitHub, Remplacer bot.py

1. **Ouvrir bot/bot.py sur GitHub**
2. **Cliquer sur Edit (crayon)**
3. **Supprimer tout le contenu**
4. **Copier le contenu de bot_new.py**
5. **Commit changes** : "Update bot.py to v2.0 with onboarding"

### Ajouter les Nouveaux Fichiers

1. **Add file** → **Upload files**
2. **Uploader** :
   - `onboarding.py`
   - `promotion.py`
   - `add_groupe_column.py`
3. **Commit changes**

### Mettre à Jour models.py

1. **Ouvrir bot/models.py**
2. **Edit (crayon)**
3. **Trouver la classe Utilisateur**
4. **Ajouter après `niveau_actuel`** :
   ```python
   groupe = Column(String(10), nullable=False, default="1-A")  # Ex: "1-A", "2-B"
   ```
5. **Commit changes** : "Add groupe column to Utilisateur model"

---

## 🗄️ ÉTAPE 2 : Migration Base de Données

### Sur Render - Service Bot

1. **Dashboard** → Votre service bot → **Shell**

2. **Exécuter la migration** :
   ```bash
   cd bot
   python add_groupe_column.py
   ```

3. **Résultat attendu** :
   ```
   ✅ Colonne 'groupe' ajoutée avec succès !
   ✅ Utilisateurs existants mis à jour !
   📊 Total utilisateurs : X
   ✅ Migration terminée avec succès !
   ```

---

## ⚙️ ÉTAPE 3 : Vérifier la Configuration Render

### Service Bot

**Render → Bot Service → Settings**

Vérifier que c'est bien :
```
Build Command:
pip install -r bot/requirements.txt

Start Command:
cd bot && python bot.py

Environment Variables:
DATABASE_URL = postgresql://...
DISCORD_TOKEN = votre_token
SITE_URL = https://votre-site-web.onrender.com (optionnel)
```

### Redéployer

1. **Manual Deploy** → **Clear build cache & deploy**
2. Attendre que les logs affichent :
   ```
   ✅ Bot connecté en tant que...
   📊 Connecté à X serveur(s)
   ✅ Y commande(s) slash synchronisée(s)
   ⏰ Scheduler de révisions initialisé
   ```

---

## ✅ ÉTAPE 4 : Tester le Système

### Test 1 : Onboarding Automatique

1. **Créer un compte Discord test** (ou demander à quelqu'un)
2. **Rejoindre le serveur**
3. **Vérifier** :
   - ✅ Rôle "Groupe 1-A" attribué automatiquement
   - ✅ Catégorie "GROUPE 1-A" créée
   - ✅ 3 salons créés :
     - `#groupe-1-a-ressources` (lecture seule)
     - `#groupe-1-a-entraide` (discussion)
     - `🔊 Groupe 1-A Vocal` (vocal)
   - ✅ Message de bienvenue reçu en MP

### Test 2 : Limitation 15 Membres

1. **Ajouter 15 membres** dans Groupe 1-A
2. **Ajouter le 16ème membre**
3. **Vérifier** :
   - ✅ Rôle "Groupe 1-B" créé automatiquement
   - ✅ Catégorie "GROUPE 1-B" créée
   - ✅ 3 salons créés pour Groupe 1-B

### Test 3 : Passage d'Examen

1. **Utilisateur va sur le site web** : `https://votre-site.onrender.com/exams`
2. **Entre son ID Discord**
3. **Passe l'examen du Niveau 1**
4. **Obtient ≥70%**

### Test 4 : Promotion Automatique

1. **Sur Discord, en tant qu'admin** :
   ```
   /check_exam_results
   ```

2. **Vérifier** :
   - ✅ Message : "✅ Résultats traités - X notifications - Y promotions"
   - ✅ Utilisateur reçoit MP de félicitations
   - ✅ Rôle "Groupe 1-A" retiré
   - ✅ Rôle "Groupe 2-A" attribué
   - ✅ Accès au nouveau salon Groupe 2-A
   - ✅ Plus d'accès au salon Groupe 1-A

### Test 5 : Échec d'Examen

1. **Utilisateur passe examen**
2. **Obtient <70%**
3. **Admin utilise** `/check_exam_results`
4. **Vérifier** :
   - ✅ Utilisateur reçoit notification en MP
   - ✅ Reste dans Groupe 1-A (pas de changement)
   - ✅ Peut retenter l'examen

---

## 📋 Nouvelles Commandes Discord

### Pour les Admins

| Commande | Description |
|----------|-------------|
| `/check_exam_results` | Vérifie et notifie tous les résultats d'examens web |
| `/stats` | Affiche les statistiques des groupes (membres par groupe) |
| `/manual_promote @user` | Promeut manuellement un utilisateur |

### Pour les Utilisateurs

| Commande | Description |
|----------|-------------|
| `/my_info` | Affiche tes informations (groupe, niveau, progression) |

---

## 🎨 Structure des Groupes

### Exemple avec 50 Utilisateurs au Niveau 1

```
GROUPE 1-A (Catégorie)
├── 📚 groupe-1-a-ressources (15 membres)
├── 💬 groupe-1-a-entraide
└── 🔊 Groupe 1-A Vocal

GROUPE 1-B (Catégorie)
├── 📚 groupe-1-b-ressources (15 membres)
├── 💬 groupe-1-b-entraide
└── 🔊 Groupe 1-B Vocal

GROUPE 1-C (Catégorie)
├── 📚 groupe-1-c-ressources (15 membres)
├── 💬 groupe-1-c-entraide
└── 🔊 Groupe 1-C Vocal

GROUPE 1-D (Catégorie)
├── 📚 groupe-1-d-ressources (5 membres)
├── 💬 groupe-1-d-entraide
└── 🔊 Groupe 1-D Vocal
```

---

## 🔄 Flux Complet Utilisateur

```
1. REJOINDRE LE SERVEUR
   ↓
   Bot détecte → Attribution automatique Groupe 1-A
   ↓
   Création salons si nécessaire
   ↓
   Message de bienvenue en MP

2. PASSER L'EXAMEN
   ↓
   Site web → Entre ID Discord
   ↓
   Examen filtré par niveau_actuel
   ↓
   Soumission → Résultat sauvegardé (notified=False)

3. NOTIFICATION RÉSULTATS
   ↓
   Admin: /check_exam_results
   ↓
   Si réussi (≥70%):
      ├─ Promotion niveau suivant
      ├─ Retrait ancien rôle
      ├─ Attribution nouveau rôle
      ├─ Accès nouveau salon
      └─ MP félicitations
   ↓
   Si échoué (<70%):
      ├─ Reste dans groupe actuel
      └─ MP notification échec

4. PROGRESSION
   ↓
   Niveau 1 → 2 → 3 → 4 → 5
   ↓
   Chaque niveau = nouveau groupe automatique
```

---

## 🐛 Dépannage

### Erreur "Column 'groupe' does not exist"

→ Migration non effectuée

**Solution** :
```bash
cd bot
python add_groupe_column.py
```

### Les Salons ne se Créent Pas

→ Permissions bot insuffisantes

**Solution** :
1. Discord → Paramètres serveur → Rôles
2. Rôle du bot → Permissions :
   - ✅ Gérer les rôles
   - ✅ Gérer les salons
   - ✅ Gérer les permissions
   - ✅ Voir les salons
   - ✅ Envoyer des messages

### Aucun Nouveau Membre ne Reçoit de Rôle

→ Intent "members" non activé

**Solution** :
1. [Discord Developer Portal](https://discord.com/developers/applications)
2. Votre app → Bot
3. Privileged Gateway Intents :
   - ✅ **Server Members Intent** (IMPORTANT)
   - ✅ Message Content Intent
   - ✅ Presence Intent
4. Save Changes
5. Redémarrer le bot sur Render

### `/check_exam_results` ne Trouve Aucun Résultat

→ Les résultats ne sont pas dans la DB

**Solution** :
1. Vérifier que le site web est bien connecté à PostgreSQL
2. Tester un examen sur le site web
3. Vérifier dans Render Shell :
   ```python
   from db_connection import SessionLocal
   from models import ExamResult
   
   db = SessionLocal()
   results = db.query(ExamResult).all()
   print(f"Résultats : {len(results)}")
   ```

---

## ✅ Checklist Complète

### GitHub
- [ ] bot.py mis à jour vers v2.0
- [ ] onboarding.py ajouté
- [ ] promotion.py ajouté
- [ ] add_groupe_column.py ajouté
- [ ] models.py modifié (colonne groupe)

### Base de Données
- [ ] Migration exécutée (add_groupe_column.py)
- [ ] Colonne 'groupe' présente dans utilisateurs
- [ ] Utilisateurs existants mis à jour

### Discord
- [ ] Intents activés (Members, Message Content, Presence)
- [ ] Permissions bot correctes
- [ ] Bot redémarré

### Tests
- [ ] Nouveau membre reçoit rôle automatiquement
- [ ] Salons créés automatiquement (3 par groupe)
- [ ] Limite 15 membres respectée (1-A → 1-B)
- [ ] Promotion après examen réussi fonctionne
- [ ] Notification échec fonctionne
- [ ] Commandes /check_exam_results, /stats, /my_info fonctionnent

---

## 🎉 Félicitations !

Votre système v2.0 est maintenant opérationnel avec :
- ✅ Onboarding automatique
- ✅ Gestion dynamique des groupes
- ✅ Promotions automatiques
- ✅ Structure complète de salons

**Le système est maintenant entièrement automatisé !** 🚀

---

## 📞 Support

En cas de problème, vérifiez :
1. Les logs Render (Build + Start)
2. Les intents Discord
3. La migration de la base de données
4. Les permissions du bot

**Consultez TROUBLESHOOTING.md pour les erreurs courantes.**
