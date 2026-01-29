# 🚀 MVP - Nouveau Système de Groupes

## ⚠️ IMPORTANT : MIGRATION REQUISE

Avant de tester le MVP, tu DOIS exécuter la migration de la base de données :

```bash
cd /home/user/projet_finale/bot
python migration_nouveau_systeme.py
```

Cette migration va :
- Ajouter les nouvelles colonnes (`is_alumni`, `in_rattrapage`)
- Rendre `cohorte_id` nullable
- Créer les nouvelles tables (`waiting_lists`, `rattrapage_exams`)

---

## 📋 FONCTIONNALITÉS IMPLÉMENTÉES

### ✅ 1. Système de Bonus (Corrigé)
- MPs privés avec nombre de votes et rang
- Suppression du message public dans "entraide"

### ✅ 2. Inscription avec Temps de Formation
- Vérification automatique du temps minimum requis
- Demande de confirmation si temps insuffisant
- Waiting list automatique si nécessaire

### ✅ 3. Waiting Lists (2 Types)
- **Type A** : Attente de création d'un nouveau groupe (7 personnes)
- **Type B** : Tous les groupes A-Z pleins

### ✅ 4. Système de Rattrapage
- **< 20%** : Assignation à un groupe normal ou waiting list
- **20-40%** : Groupe rattrapage + délai de 3/4 du temps de formation
- **40-60%** : Groupe rattrapage + délai de 1/2 du temps de formation
- **> 60%** : Groupe rattrapage + délai de 1/4 du temps de formation

### ✅ 5. Promotions et Alumni
- Promotion automatique au niveau suivant
- Status Alumni quand niveau 5 terminé

---

## 🔧 FICHIERS MODIFIÉS

### Bot Discord
- `bot/onboarding.py` : Utilise GroupManager pour l'inscription
- `bot/bonus_system.py` : Notifications de bonus corrigées
- `bot/models.py` : Nouveaux modèles (WaitingList, RattrapageExam)

### Site Web
- `web/app.py` : Utilise GroupManager pour submit_exam (promotions + échecs)

### Nouveaux Fichiers
- `bot/cohort_config.py` : Configuration centralisée
- `bot/group_manager.py` : Gestionnaire principal
- `bot/migration_nouveau_systeme.py` : Script de migration

---

## 🧪 COMMENT TESTER

### Test 1 : Inscription Normale
1. Rejoins le serveur Discord avec un nouveau compte
2. Le bot devrait t'assigner automatiquement au groupe 1-A
3. Tu reçois un MP de bienvenue

### Test 2 : Inscription avec Temps Insuffisant
1. Crée un examen pour le groupe 1-A dans moins de 48h :
```bash
/create_exam_period group:1 start_time:"2026-01-29 14:00"
```
2. Rejoins le serveur avec un nouveau compte
3. Tu devrais recevoir un message de confirmation (✅ ou ❌)

### Test 3 : Échec d'Examen
1. Passe un examen et rate avec 45%
2. Vérifie dans la console : tu es assigné au groupe "Rattrapage Niveau 1"
3. Le délai devrait être de 1.5 jours (40-60% = 1/2 de 3 jours)

### Test 4 : Réussite d'Examen
1. Passe un examen et réussis avec 75%
2. Vérifie dans la console : promotion au niveau 2
3. Nouveau groupe assigné (ex: 2-A, 2-B...)

### Test 5 : Niveau 5 → Alumni
1. Mets ton utilisateur au niveau 5 manuellement (via psql)
2. Passe l'examen du niveau 5 avec succès
3. Vérifie que `is_alumni = true` dans la base

---

## 📊 COMMANDES DISCORD À CRÉER (TODO)

Ces commandes ne sont PAS encore implémentées :

```
/group_info [user_id]           # Affiche les infos de groupe d'un utilisateur
/waiting_list [niveau]          # Affiche la waiting list d'un niveau
/rattrapage_info [user_id]      # Affiche les infos de rattrapage
/process_waiting_lists          # Force le traitement des waiting lists
/actualiser_exams [user_id]     # Actualise les rôles Discord après promotion/échec
```

---

## 🐛 PROBLÈMES CONNUS

### 1. Rôles Discord Non Synchronisés
Après une promotion ou un échec, les rôles Discord ne sont PAS automatiquement mis à jour.
**Solution temporaire** : Utilise `/actualiser_exams` (à créer)

### 2. Salons de Rattrapage Non Créés
Les salons "Rattrapage Niveau X" ne sont pas créés automatiquement.
**Solution temporaire** : Crée-les manuellement sur Discord

### 3. Gestion des Réactions (Confirmation)
Le système de confirmation par réaction n'est pas encore branché dans `bot.py`.
**Solution** : Ajouter un event handler pour `on_raw_reaction_add`

---

## 📈 PROCHAINES ÉTAPES

### Pour Avoir un MVP Complet :
1. ✅ Migration de la base de données
2. ✅ Intégration dans onboarding.py
3. ✅ Intégration dans web/app.py (submit_exam)
4. ❌ Event handler pour les réactions de confirmation
5. ❌ Commandes Discord de gestion
6. ❌ Création automatique des salons de rattrapage
7. ❌ Synchronisation automatique des rôles Discord
8. ❌ Notifications par MP lors des changements

### Pour la Production :
1. Tests approfondis de tous les cas
2. Gestion des erreurs et edge cases
3. Logs détaillés
4. Documentation utilisateur
5. Interface web pour visualiser les groupes/waiting lists

---

## 🔍 VÉRIFICATIONS MANUELLES

### Vérifier un Utilisateur
```sql
SELECT user_id, username, niveau_actuel, groupe, is_alumni, in_rattrapage
FROM utilisateurs
WHERE user_id = YOUR_USER_ID;
```

### Vérifier la Waiting List
```sql
SELECT * FROM waiting_lists
WHERE niveau = 1;
```

### Vérifier les Rattrapages
```sql
SELECT * FROM rattrapage_exams
WHERE completed = false;
```

### Vérifier les Périodes d'Examen
```sql
SELECT id, group_number, groupe, start_time, end_time, is_rattrapage
FROM exam_periods
ORDER BY start_time DESC
LIMIT 10;
```

---

## ❓ EN CAS DE PROBLÈME

1. Vérifie que la migration a bien été exécutée
2. Regarde les logs dans la console du bot
3. Vérifie la base de données manuellement
4. Assure-toi que `cohort_config.py` est bien importé
5. Vérifie que les permissions Discord sont correctes

---

## 📞 CONTACT

Si tu rencontres un bug ou as une question, note :
- Le comportement observé
- Le comportement attendu
- Les logs de la console
- L'état de la base de données

Bon test ! 🚀
