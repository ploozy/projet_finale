# 📝 Changements Apportés au Système

Ce document liste toutes les corrections et améliorations apportées au MVP.

---

## 🔴 Phase 1: Corrections Critiques

### ✅ Paliers de Votes Corrigés
**Avant:**
- Or (8+ votes): +20%
- Argent (5-7 votes): +12%
- Bronze (3-4 votes): +6%

**Après:**
- Or (7+ votes): +10%
- Argent (4-6 votes): +8%
- Bronze (1-3 votes): +5%

**Fichiers modifiés:** `bot/vote_system.py`

### ✅ Obligation de 3 Votes
- **Avant:** 1 à 3 votes acceptés
- **Après:** Exactement 3 votes OBLIGATOIRES

**Fichiers modifiés:** `bot/vote_system.py`

### ✅ Nettoyage exam.json
- Suppression des champs `start_date` et `end_date` (non utilisés)
- Le système utilise uniquement `ExamPeriod` pour les fenêtres de 6h

**Fichiers modifiés:** `web/exam.json`

---

## 🟠 Phase 2: Système de Votes 24h Avant

### ✅ Ouverture des Votes 24h Avant l'Examen
- Ajout du champ `vote_start_time` dans `ExamPeriod`
- Les votes s'ouvrent 24 heures avant le début de l'examen
- Les votes restent ouverts jusqu'à la fin de l'examen (6h)

**Fichiers modifiés:**
- `bot/models.py` et `web/models.py`
- `bot/bot.py` (commande `/create_exam_period`)
- `bot/vote_system.py`

**Migration DB:** Exécuter `python bot/add_vote_start_time.py` une fois

---

## 🟡 Phase 3: Correction Promotion Automatique

### ✅ Recherche de Groupe Disponible
**Avant:** Les utilisateurs promus étaient toujours placés dans le groupe A du niveau suivant

**Après:** Le système cherche le premier groupe disponible avec moins de 15 membres (A, B, C...)

**Fonctionnement:**
1. Compte les membres de chaque groupe
2. Retourne le premier groupe avec < 15 membres
3. Si tous pleins, crée un nouveau groupe (K, L...)

**Fichiers modifiés:** `web/app.py`

---

## 🟢 Phase 4: Nettoyage Commandes

### ✅ Optimisation send_course
- **Supprimé:** `/send_course_manual` (redondant)
- **Conservé:** `/send_course` (channel optionnel)
- **Optimisé:** `send_course_to_channel()` utilise les données en mémoire

**Fichiers modifiés:** `bot/bot.py`

---

## 📊 Statut du MVP

✅ **Fonctionnel:**
- Onboarding automatique
- Système de votes avec bonus
- Examens web avec promotion automatique
- Révision espacée (SM-2)
- Notifications automatiques

⚠️ **Limitations:**
- Pas de système Toboggan (échecs restent dans même groupe)
- Pas de décalage automatique des examens
- Système de cohortes encore présent (non utilisé)

🎯 **Prêt pour:** Tests avec utilisateurs réels (petite échelle)

---

## 🚀 Utilisation

### Commandes Principales
- `/create_exam_period <group> <date>` - Créer fenêtre 6h (admin)
- `/send_course <id> [channel]` - Envoyer cours (admin)
- `/vote @u1 @u2 @u3` - Voter (3 obligatoire)
- `/my_info` - Voir ses infos
