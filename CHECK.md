# ✅ Liste de Vérification - Système de Formation

## 🔧 Avant le Déploiement

### PostgreSQL
- [ ] Base de données créée sur Render
- [ ] URL de connexion copiée
- [ ] Variables d'environnement configurées

### Discord Bot
- [ ] Token Discord obtenu
- [ ] Intents activés (Message Content, Server Members, Presence)
- [ ] Bot invité sur le serveur
- [ ] Permissions administrateur accordées

### Fichiers de Configuration
- [ ] `exam.json` - Dates d'examens configurées
- [ ] `config.json` - Cours et questions configurés
- [ ] `courses_content.json` - Contenu des cours rempli

---

## 🚀 Après le Déploiement

### Bot Discord

#### Démarrage
- [ ] Le bot se connecte sans erreur
- [ ] Message `✅ Bot connecté en tant que...` dans les logs
- [ ] Message `✅ Serveur HTTP démarré sur port 8080` dans les logs
- [ ] Message `⏰ Scheduler de révisions initialisé` dans les logs

#### Fonctionnalités
- [ ] `/send_course 1` envoie un embed avec bouton
- [ ] Clic sur "Démarrer le QCM" envoie le quiz en MP
- [ ] Les réponses sont bien enregistrées
- [ ] Les révisions sont programmées correctement
- [ ] `/check_exam_results` notifie les résultats web

#### Base de Données
- [ ] Les utilisateurs sont créés dans `utilisateurs`
- [ ] Les cohortes sont générées automatiquement
- [ ] Les résultats de quiz sont sauvegardés dans `reviews`

---

### Site Web

#### Démarrage
- [ ] Le site web démarre sans erreur
- [ ] Message `✅ Connexion PostgreSQL réussie` dans les logs
- [ ] Port 5000 accessible

#### Page d'Accueil
- [ ] `https://votre-site.onrender.com/` affiche la page
- [ ] Le bouton "Passer un examen" fonctionne

#### Page Cours
- [ ] `https://votre-site.onrender.com/course/1` affiche le cours
- [ ] Le contenu est bien formaté
- [ ] Les exemples de code sont affichés correctement

#### Page Examens - Formulaire
- [ ] `https://votre-site.onrender.com/exams` affiche le formulaire
- [ ] Saisie d'un ID invalide → Message d'erreur
- [ ] Saisie d'un ID non inscrit → "Utilisateur non trouvé"
- [ ] Saisie d'un ID valide → Redirection vers l'examen

#### Page Examens - Vérification Groupe
- [ ] Utilisateur groupe 1 → Examen groupe 1
- [ ] Utilisateur groupe 2 → Examen groupe 2
- [ ] Utilisateur groupe 3 → Examen groupe 3
- [ ] etc.

#### Page Examens - Vérification Dates
- [ ] Avant `start_date` → "L'examen n'est pas encore ouvert"
- [ ] Entre `start_date` et `end_date` → Examen affiché
- [ ] Après `end_date` → "L'examen est terminé"

#### Page Examens - Interface
- [ ] Timer fonctionne correctement
- [ ] Les questions s'affichent
- [ ] Les choix multiples sont cliquables
- [ ] Le bouton "Soumettre" fonctionne

#### Page Examens - Soumission
- [ ] Score calculé correctement
- [ ] Résultat sauvegardé dans `exam_results`
- [ ] Écran de résultat affiché (réussi/échoué)
- [ ] Niveau utilisateur mis à jour si réussi
- [ ] L'utilisateur peut revenir à `/exams`

#### Notifications Discord
- [ ] `/check_exam_results` récupère les résultats non notifiés
- [ ] Les résultats sont envoyés en MP Discord
- [ ] Les résultats sont marqués comme `notified=True`

---

## 🗃️ Base de Données

### Tables Créées
- [ ] `cohortes` existe
- [ ] `utilisateurs` existe
- [ ] `calendrier_examens` existe
- [ ] `historique_cohortes` existe
- [ ] `reviews` existe
- [ ] `exam_results` existe

### Données de Test
- [ ] Au moins 1 utilisateur dans `utilisateurs`
- [ ] Au moins 1 cohorte dans `cohortes`
- [ ] Au moins 1 résultat dans `exam_results`

### Requêtes SQL de Vérification

```sql
-- Vérifier les utilisateurs
SELECT * FROM utilisateurs LIMIT 5;

-- Vérifier les cohortes
SELECT * FROM cohortes;

-- Vérifier les examens passés
SELECT user_id, exam_id, score, total, passed, date 
FROM exam_results 
ORDER BY date DESC 
LIMIT 10;

-- Vérifier les révisions
SELECT * FROM reviews LIMIT 10;
```

---

## 🔍 Tests Fonctionnels

### Scénario 1 : Inscription

1. [ ] Utilisateur rejoint le serveur Discord
2. [ ] Admin lance `/send_course 1`
3. [ ] Utilisateur clique sur "Démarrer le QCM"
4. [ ] Utilisateur répond aux questions
5. [ ] Utilisateur est créé dans `utilisateurs` avec `niveau_actuel=1`
6. [ ] Utilisateur est assigné à une cohorte

### Scénario 2 : Examen Web - Succès

1. [ ] Utilisateur va sur `/exams`
2. [ ] Entre son ID Discord
3. [ ] Examen du groupe 1 s'affiche (si niveau_actuel=1)
4. [ ] Utilisateur répond et obtient >= 70%
5. [ ] Résultat sauvegardé avec `passed=True`
6. [ ] `niveau_actuel` passe à 2
7. [ ] Admin lance `/check_exam_results`
8. [ ] Utilisateur reçoit notification Discord "Réussi"

### Scénario 3 : Examen Web - Échec

1. [ ] Utilisateur va sur `/exams`
2. [ ] Entre son ID Discord
3. [ ] Examen s'affiche
4. [ ] Utilisateur répond et obtient < 70%
5. [ ] Résultat sauvegardé avec `passed=False`
6. [ ] `niveau_actuel` ne change pas
7. [ ] Admin lance `/check_exam_results`
8. [ ] Utilisateur reçoit notification Discord "Non validé"

### Scénario 4 : Révisions Espacées

1. [ ] Utilisateur répond à un quiz Discord
2. [ ] Révision créée dans `reviews` avec `next_review` à J+2
3. [ ] Attendre 2 jours (ou modifier `next_review`)
4. [ ] Le scheduler envoie automatiquement la révision en MP

### Scénario 5 : Gestion des Dates

1. [ ] Utilisateur groupe 1 essaie d'accéder à l'examen avant `start_date`
   - [ ] Message : "L'examen n'est pas encore ouvert"
2. [ ] Modifier `start_date` à maintenant - 1 jour
3. [ ] Modifier `end_date` à maintenant + 7 jours
4. [ ] Utilisateur groupe 1 accède à l'examen
   - [ ] Examen s'affiche correctement
5. [ ] Modifier `end_date` à maintenant - 1 jour
6. [ ] Utilisateur groupe 1 essaie d'accéder
   - [ ] Message : "L'examen est terminé"

---

## 🐛 Tests d'Erreurs

### Erreurs Bot
- [ ] Token Discord invalide → Erreur de connexion
- [ ] DATABASE_URL invalide → Erreur PostgreSQL
- [ ] Utilisateur bloque les MPs → Message d'erreur approprié

### Erreurs Web
- [ ] ID Discord non numérique → "ID invalide"
- [ ] ID Discord inexistant → "Utilisateur non trouvé"
- [ ] Aucun examen pour le groupe → "Aucun examen disponible"
- [ ] Examen hors dates → Message de date approprié

### Erreurs Base de Données
- [ ] Tables non créées → `init_db.py` doit être lancé
- [ ] Connexion échouée → Vérifier DATABASE_URL

---

## 📊 Performance

### Bot Discord
- [ ] Temps de réponse aux commandes < 2s
- [ ] MP envoyés instantanément
- [ ] Pas de crash après plusieurs heures

### Site Web
- [ ] Page d'accueil charge en < 1s
- [ ] Soumission d'examen < 3s
- [ ] Pas d'erreur 500 après plusieurs requêtes

---

## 🔒 Sécurité

- [ ] `.env` n'est pas commité
- [ ] Tokens dans variables d'environnement uniquement
- [ ] Aucun secret en dur dans le code
- [ ] Permissions Discord limitées au nécessaire
- [ ] SQL queries protégées (SQLAlchemy ORM)

---

## 📝 Documentation

- [ ] README.md complet et à jour
- [ ] DEPLOY.md avec instructions claires
- [ ] CHECK.md (ce fichier) rempli
- [ ] Commentaires dans le code

---

## ✅ Résumé Final

Tout est ✅ ? Félicitations ! Votre système est opérationnel ! 🎉

Quelque chose ne fonctionne pas ? 
→ Consultez DEPLOY.md section "Résolution de Problèmes"
