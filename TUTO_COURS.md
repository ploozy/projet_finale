# Tutoriel Complet : Modifier les Cours d'Arabe

Ce guide t'explique comment personnaliser les leçons, exercices et la structure des cours.

---

## Structure des Fichiers

```
web/
├── app.py                      # Routes + Contenu des leçons (LESSONS_DATA)
├── arabic_courses.json         # Configuration des cours (titres, niveaux)
└── templates/
    ├── courses_id.html         # Page de saisie de l'ID Discord
    ├── courses_main.html       # Liste des cours (grille principale)
    ├── course_lesson.html      # Affichage d'une leçon (étapes)
    └── course_exercises.html   # Fiches d'exercices (QCM + traductions)
```

---

## 1. Modifier le Contenu des Leçons

### Fichier : `web/app.py`

Le contenu des leçons est dans le dictionnaire `LESSONS_DATA` (vers la ligne 50+).

### Structure d'une leçon :

```python
LESSONS_DATA = {
    1: {  # ID de la leçon
        "title": "L'alphabet arabe - Partie 1",
        "description": "Les 7 premières lettres",
        "steps": [
            {
                "title": "Introduction",
                "type": "theory",  # Types: "theory", "practice", "exercise"
                "content": """
                    <p>Texte d'introduction...</p>
                    <div class="letter-box">
                        <span class="arabic-large">أ</span>
                        <span class="letter-name">Alif</span>
                        <span class="pronunciation">/a/</span>
                    </div>
                """
            },
            {
                "title": "Exercice",
                "type": "exercise",
                "content": "..."
            }
        ]
    },
    2: { ... },  # Leçon 2
    3: { ... },  # etc.
}
```

### Pour ajouter/modifier une étape :

```python
{
    "title": "Titre de l'étape",
    "type": "theory",  # ou "practice" ou "exercise"
    "content": """
        <p>Mon contenu HTML ici</p>
    """
}
```

---

## 2. Modifier l'Apparence des Boîtes de Lettres

### Fichier : `web/templates/course_lesson.html`

Les styles CSS sont dans la balise `<style>` en haut du fichier.

### Boîte de lettre standard :

```css
.letter-box {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 20px;          /* Coins arrondis */
    padding: 30px;                /* Espacement intérieur */
    text-align: center;
    color: white;
    margin: 15px;
    min-width: 150px;
    box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
    transition: transform 0.3s ease;
}

.letter-box:hover {
    transform: translateY(-5px) scale(1.02);  /* Animation au survol */
}
```

### Pour changer les couleurs :

```css
/* Dégradé violet → bleu */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* Dégradé vert */
background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);

/* Dégradé orange */
background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);

/* Couleur unie */
background: #3498db;
```

### Pour changer la taille des lettres arabes :

```css
.arabic-large {
    font-size: 72px;      /* Taille de la lettre */
    font-family: 'Amiri', 'Traditional Arabic', serif;
    display: block;
    margin-bottom: 15px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
}
```

### Pour changer l'arrangement (grille) :

```css
.letters-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);  /* 4 colonnes */
    gap: 20px;                              /* Espacement */
    margin: 30px 0;
}

/* Pour 3 colonnes : */
grid-template-columns: repeat(3, 1fr);

/* Pour 2 colonnes : */
grid-template-columns: repeat(2, 1fr);

/* Colonnes de tailles différentes : */
grid-template-columns: 1fr 2fr 1fr;  /* Milieu plus large */
```

---

## 3. Modifier la Grille des Cours (Page Principale)

### Fichier : `web/templates/courses_main.html`

### Grille des cours :

```css
.courses-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 25px;
    margin-top: 30px;
}
```

### Carte de cours :

```css
.course-card {
    background: white;
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
    border: 1px solid #eee;
}

.course-card:hover {
    transform: translateY(-10px);
    box-shadow: 0 20px 60px rgba(0,0,0,0.15);
}
```

### Carte verrouillée :

```css
.course-card.locked {
    opacity: 0.6;
    filter: grayscale(30%);
}

.course-card.locked::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.1);
    border-radius: 20px;
}
```

---

## 4. Modifier les Fiches d'Exercices

### Fichier : `web/templates/course_exercises.html`

### Style des questions QCM :

```css
.question-card {
    background: white;
    border-radius: 15px;
    padding: 25px;
    margin-bottom: 25px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.08);
}

.question-text {
    font-size: 1.2rem;
    color: #2d3748;
    margin-bottom: 20px;
    font-weight: 600;
}
```

### Style des options de réponse :

```css
.option-btn {
    display: block;
    width: 100%;
    padding: 15px 20px;
    margin: 10px 0;
    background: #f7fafc;
    border: 2px solid #e2e8f0;
    border-radius: 10px;
    text-align: left;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s ease;
}

.option-btn:hover {
    background: #edf2f7;
    border-color: #cbd5e0;
}

.option-btn.selected {
    background: #ebf8ff;
    border-color: #4299e1;
    color: #2b6cb0;
}

.option-btn.correct {
    background: #c6f6d5;
    border-color: #48bb78;
}

.option-btn.incorrect {
    background: #fed7d7;
    border-color: #fc8181;
}
```

---

## 5. Modifier la Configuration des Cours

### Fichier : `web/arabic_courses.json`

```json
{
  "levels": {
    "1": {
      "name": "Niveau 1 - Débutant",
      "description": "Les bases de l'alphabet arabe",
      "min_training_days": 2,
      "lessons": [
        {
          "id": 1,
          "title": "L'alphabet arabe - Partie 1",
          "description": "Les 7 premières lettres"
        },
        {
          "id": 2,
          "title": "L'alphabet arabe - Partie 2",
          "description": "Les 7 lettres suivantes"
        },
        {
          "id": 3,
          "title": "L'alphabet arabe - Partie 3",
          "description": "Les 14 dernières lettres"
        }
      ],
      "exercises": [
        {
          "id": 1,
          "title": "Fiche d'exercices - Niveau 1",
          "description": "QCM et exercices de reconnaissance"
        }
      ]
    },
    "2": {
      "name": "Niveau 2 - Intermédiaire",
      ...
    }
  }
}
```

### Pour ajouter un nouveau niveau :

```json
"3": {
  "name": "Niveau 3 - Avancé",
  "description": "Grammaire et conjugaison",
  "min_training_days": 5,
  "lessons": [
    { "id": 7, "title": "...", "description": "..." }
  ],
  "exercises": [
    { "id": 3, "title": "...", "description": "..." }
  ]
}
```

---

## 6. Les Polices Utilisées

### Dans tous les templates :

```html
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&display=swap" rel="stylesheet">
```

### Utilisation :

```css
/* Texte général (français) */
font-family: 'Poppins', sans-serif;

/* Texte arabe */
font-family: 'Amiri', 'Traditional Arabic', serif;
```

### Pour changer la police arabe :

Options recommandées :
- `'Amiri'` - Élégante, style Naskh
- `'Scheherazade New'` - Traditionnelle
- `'Noto Naskh Arabic'` - Moderne, lisible
- `'Cairo'` - Sans-serif moderne

```html
<!-- Ajouter dans <head> -->
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
```

```css
.arabic-large {
    font-family: 'Cairo', sans-serif;
}
```

---

## 7. Exemples de Modifications Courantes

### A. Changer la couleur du header

**Fichier** : `course_lesson.html`, `courses_main.html`

```css
.header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    /* Remplacer par : */
    background: linear-gradient(135deg, #2d3436 0%, #000000 100%);  /* Noir */
    background: linear-gradient(135deg, #0f4c75 0%, #3282b8 100%);  /* Bleu */
}
```

### B. Agrandir les boîtes de lettres

```css
.letter-box {
    padding: 40px;        /* Plus grand (était 30px) */
    min-width: 180px;     /* Plus large (était 150px) */
}

.arabic-large {
    font-size: 90px;      /* Plus grand (était 72px) */
}
```

### C. Changer l'arrangement : 2 colonnes au lieu de 4

```css
.letters-grid {
    grid-template-columns: repeat(2, 1fr);  /* 2 colonnes */
    gap: 30px;                              /* Plus d'espace */
}
```

### D. Ajouter une bordure aux cartes

```css
.course-card {
    border: 3px solid #667eea;  /* Bordure violette */
}
```

### E. Effet de survol plus prononcé

```css
.letter-box:hover {
    transform: translateY(-10px) scale(1.1) rotate(2deg);
    box-shadow: 0 20px 50px rgba(102, 126, 234, 0.5);
}
```

---

## 8. Ajouter une Nouvelle Leçon

### Étape 1 : Ajouter le contenu dans `app.py`

```python
LESSONS_DATA = {
    # ... leçons existantes ...

    7: {  # Nouvelle leçon
        "title": "Ma nouvelle leçon",
        "description": "Description courte",
        "steps": [
            {
                "title": "Étape 1",
                "type": "theory",
                "content": """
                    <p>Contenu de l'étape 1...</p>
                """
            },
            {
                "title": "Étape 2",
                "type": "practice",
                "content": """
                    <p>Exercice pratique...</p>
                """
            }
        ]
    }
}
```

### Étape 2 : Ajouter dans `arabic_courses.json`

```json
{
  "id": 7,
  "title": "Ma nouvelle leçon",
  "description": "Description courte"
}
```

---

## 9. Structure HTML des Boîtes de Lettres

### Boîte simple :

```html
<div class="letter-box">
    <span class="arabic-large">ب</span>
    <span class="letter-name">Ba</span>
    <span class="pronunciation">/b/</span>
</div>
```

### Boîte avec formes de la lettre :

```html
<div class="letter-box">
    <span class="arabic-large">ب</span>
    <span class="letter-name">Ba</span>
    <div class="letter-forms">
        <span>Isolée: ب</span>
        <span>Initiale: بـ</span>
        <span>Médiane: ـبـ</span>
        <span>Finale: ـب</span>
    </div>
</div>
```

### Boîte avec exemple de mot :

```html
<div class="letter-box">
    <span class="arabic-large">ب</span>
    <span class="letter-name">Ba</span>
    <div class="example-word">
        <span class="arabic-word">باب</span>
        <span class="translation">porte</span>
    </div>
</div>
```

---

## 10. Couleurs Recommandées

### Dégradés :

```css
/* Violet (actuel) */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* Bleu océan */
background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%);

/* Vert nature */
background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);

/* Rose sunset */
background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);

/* Or premium */
background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%);

/* Rouge passion */
background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);

/* Noir élégant */
background: linear-gradient(135deg, #232526 0%, #414345 100%);
```

### Couleurs unies :

```css
--primary: #667eea;     /* Violet */
--success: #48bb78;     /* Vert */
--warning: #f6ad55;     /* Orange */
--danger: #fc8181;      /* Rouge */
--info: #4299e1;        /* Bleu */
```

---

## Résumé Rapide

| Ce que tu veux modifier | Fichier | Section |
|------------------------|---------|---------|
| Contenu des leçons | `app.py` | `LESSONS_DATA` |
| Titres des cours | `arabic_courses.json` | `lessons[].title` |
| Style des boîtes | `course_lesson.html` | CSS `.letter-box` |
| Grille de lettres | `course_lesson.html` | CSS `.letters-grid` |
| Page principale | `courses_main.html` | CSS `.courses-grid` |
| Exercices QCM | `course_exercises.html` | CSS `.question-card` |
| Polices | Tous les templates | `<link>` dans `<head>` |

---

**Astuce** : Pour tester tes modifications rapidement, modifie le CSS directement dans l'inspecteur de ton navigateur (F12), puis reporte les changements dans les fichiers.
