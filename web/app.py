"""
Site Web - Version Finale
1. Entre ton ID → Affiche TON examen automatiquement
2. Promotion automatique après réussite
3. Cours d'arabe filtré par niveau
"""

from flask import Flask, render_template, request, jsonify, session
import json
from datetime import datetime, timezone, timedelta
import os
from db_connection import SessionLocal
from models import Utilisateur, ExamResult, ExamPeriod
from sqlalchemy import func
import exercise_types
import requests
from group_manager import GroupManager

app = Flask(__name__)
app.secret_key = 'secret'

# Charger les examens
with open('exam.json', 'r', encoding='utf-8') as f:
    exams_data = json.load(f)

# Charger les cours d'arabe
with open('arabic_courses.json', 'r', encoding='utf-8') as f:
    arabic_courses = json.load(f)

# Charger les données des leçons depuis lessons.js (copié du dossier courses/)
LESSONS_DATA = {
    1: {
        "title": "الدرس الأول - Les noms démonstratifs (هذا)",
        "xp": 50,
        "steps": [
            {"type": "theory", "content": """<div class="audio-hint"><span class="audio-hint-icon">🔊</span><span>Clique sur les mots arabes pour entendre leur prononciation !</span></div><div class="theory-section"><h3 class="theory-title">📚 Introduction aux types de mots</h3><div class="theory-content"><p>En arabe, les mots (الكَلِمَةُ) se divisent en <strong>trois catégories</strong> :</p><div class="grammar-box"><h4>📝 Les trois types de mots</h4><table class="vocab-table"><thead><tr><th>Arabe</th><th>Français</th><th>Définition</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">اِسْمٌ</td><td>Nom</td><td>Indique un sens par lui-même</td></tr><tr><td class="vocab-arabic arabic">فِعْلٌ</td><td>Verbe</td><td>Indique une action et un temps</td></tr><tr><td class="vocab-arabic arabic">حَرْفٌ</td><td>Particule</td><td>N'a de sens qu'avec un autre mot</td></tr></tbody></table></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Le démonstratif هذا</h3><div class="theory-content"><div class="arabic-example"><div class="arabic-word arabic">هَذَا</div><div class="arabic-translation">Ceci / Celui-ci</div></div><p><span class="arabic">هَذَا</span> est un <strong>nom démonstratif</strong> (اِسْمُ إشَارَةٍ). Il s'utilise pour :</p><div class="grammar-box"><h4>✅ Conditions d'utilisation</h4><ul style="list-style:none;padding:0;"><li>• <strong class="arabic">مُفْرَد</strong> - Singulier</li><li>• <strong class="arabic">مُذَكَّر</strong> - Masculin</li><li>• <strong class="arabic">قَرِيب</strong> - Proche</li></ul></div><div class="arabic-example"><div class="arabic-word arabic">هَذَا كَلْبٌ</div><div class="arabic-translation">Ceci est un chien</div></div></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice pratique</h3><div class="exercise-question"><p>Comment dit-on "Ceci est un livre" en arabe ?</p></div><div class="options-grid"><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">ذلِكَ كِتَابٌ</span></button><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">هَذَا كِتَابٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَا كِتَابٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَنْ كِتَابٌ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Vocabulaire : Singulier et Pluriel</h3><div class="theory-content"><div class="warning-box"><h4>⚠️ Particularité orthographique</h4><p>Le alif après le ه se prononce mais ne s'écrit pas :</p><div class="arabic-example"><div class="arabic-word arabic">هَذَا = هَاذَا</div></div></div><table class="vocab-table"><thead><tr><th>Singulier</th><th>Pluriel</th><th>Traduction</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">كِتَابٌ</td><td class="vocab-arabic arabic">كُتُبٌ</td><td>Livre(s)</td></tr><tr><td class="vocab-arabic arabic">مَسْجِدٌ</td><td class="vocab-arabic arabic">مَسَاجِدُ</td><td>Mosquée(s)</td></tr><tr><td class="vocab-arabic arabic">بَيْتٌ</td><td class="vocab-arabic arabic">بُيُوتٌ</td><td>Maison(s)</td></tr><tr><td class="vocab-arabic arabic">قَلَمٌ</td><td class="vocab-arabic arabic">أَقْلَامٌ</td><td>Stylo(s)</td></tr></tbody></table></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice final</h3><div class="exercise-question"><p>Quel est le pluriel de <span class="arabic" style="font-size:1.5rem;color:var(--primary);">بَابٌ</span> (porte) ?</p></div><div class="options-grid"><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">بُيُوتٌ</span></button><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">أَبْوَابٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">كُتُبٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَفَاتِحُ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""}
        ]
    },
    2: {
        "title": "الدرس الثاني - L'interrogatif",
        "xp": 60,
        "steps": [
            {"type": "theory", "content": """<div class="audio-hint"><span class="audio-hint-icon">🔊</span><span>Clique sur les mots arabes pour entendre leur prononciation !</span></div><div class="theory-section"><h3 class="theory-title">📚 L'interrogatif (الاِسْتِفْهَامُ)</h3><div class="theory-content"><p>Pour poser des questions en arabe :</p><div class="grammar-box"><h4>📝 Les particules et noms interrogatifs</h4><table class="vocab-table"><thead><tr><th>Arabe</th><th>Type</th><th>Traduction</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">أَ</td><td>Particule</td><td>Est-ce que ?</td></tr><tr><td class="vocab-arabic arabic">مَا</td><td>Nom</td><td>Qu'est-ce que ?</td></tr><tr><td class="vocab-arabic arabic">مَنْ</td><td>Nom</td><td>Qui est-ce ?</td></tr></tbody></table></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 La hamza interrogative (أَ)</h3><div class="theory-content"><div class="arabic-example"><div class="arabic-word arabic">أَ</div><div class="arabic-translation">Est-ce que ?</div></div><div class="grammar-box"><h4>✅ Comment répondre ?</h4><ul style="list-style:none;padding:0;"><li>• <span class="arabic" style="color:var(--success);font-size:1.3rem;">نَعَمْ</span> - Oui</li><li>• <span class="arabic" style="color:var(--accent);font-size:1.3rem;">لَا</span> - Non</li></ul></div><div class="arabic-example"><div class="arabic-word arabic">أَهَذَا كِتَابٌ؟</div><div class="arabic-translation">Est-ce que ceci est un livre ?</div></div></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice pratique</h3><div class="exercise-question"><p class="arabic" style="font-size:2rem;color:var(--primary);">أَهَذَا بَيْتٌ؟</p><p>(En regardant une mosquée)</p></div><div class="options-grid"><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">لَا، هَذَا مَسْجِدٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">نَعَمْ، هَذَا بَيْتٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَا هَذَا</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَنْ هَذَا</span></button></div><div class="feedback-message" id="feedback"></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 مَا vs مَنْ</h3><div class="theory-content"><div class="grammar-box"><h4>🔑 Différence clé</h4><table class="vocab-table"><thead><tr><th>Interrogatif</th><th>Utilisation</th><th>Exemple</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">مَا</td><td>Non-humain</td><td class="vocab-arabic arabic">مَا هَذَا؟ هَذَا كَلْبٌ</td></tr><tr><td class="vocab-arabic arabic">مَنْ</td><td>Humain</td><td class="vocab-arabic arabic">مَنْ هَذَا؟ هَذَا طَبِيبٌ</td></tr></tbody></table></div></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice pratique</h3><div class="exercise-question"><p>Pour demander "Qui est cet enseignant ?", j'utilise :</p></div><div class="options-grid"><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَا هَذَا المُدَرِّسُ؟</span></button><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">مَنْ هَذَا المُدَرِّسُ؟</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">أَهَذَا مُدَرِّسٌ؟</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">هَذَا مُدَرِّسٌ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Vocabulaire</h3><div class="theory-content"><table class="vocab-table"><thead><tr><th>Singulier</th><th>Pluriel</th><th>Traduction</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">طَبِيبٌ</td><td class="vocab-arabic arabic">أَطِبَّاءُ</td><td>Médecin(s)</td></tr><tr><td class="vocab-arabic arabic">مُدَرِّسٌ</td><td class="vocab-arabic arabic">مُدَرِّسُونَ</td><td>Enseignant(s)</td></tr><tr><td class="vocab-arabic arabic">طَالِبٌ</td><td class="vocab-arabic arabic">طُلَّابٌ</td><td>Étudiant(s)</td></tr><tr><td class="vocab-arabic arabic">كَلْبٌ</td><td class="vocab-arabic arabic">كِلَابٌ</td><td>Chien(s)</td></tr></tbody></table></div></div>"""}
        ]
    },
    3: {
        "title": "الدرس الثالث - Le démonstratif éloigné (ذلك)",
        "xp": 50,
        "steps": [
            {"type": "theory", "content": """<div class="audio-hint"><span class="audio-hint-icon">🔊</span><span>Clique sur les mots arabes pour entendre leur prononciation !</span></div><div class="theory-section"><h3 class="theory-title">📚 Le démonstratif ذَلِكَ</h3><div class="theory-content"><div class="arabic-example"><div class="arabic-word arabic">ذَلِكَ</div><div class="arabic-translation">Cela / Celui-là</div></div><p><span class="arabic">ذَلِكَ</span> s'utilise pour désigner quelque chose qui est :</p><div class="grammar-box"><h4>✅ Conditions d'utilisation</h4><ul style="list-style:none;padding:0;"><li>• <strong class="arabic">مُفْرَد</strong> - Singulier</li><li>• <strong class="arabic">مُذَكَّر</strong> - Masculin</li><li>• <strong class="arabic" style="color:var(--accent);">بَعِيد</strong> - <strong>Éloigné</strong></li></ul></div><div class="arabic-example"><div class="arabic-word arabic">ذَلِكَ نَجْمٌ</div><div class="arabic-translation">Cela est une étoile (loin)</div></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Différence entre هَذَا et ذَلِكَ</h3><div class="theory-content"><div class="grammar-box"><h4>🔑 La seule différence : la distance</h4><table class="vocab-table"><thead><tr><th>Démonstratif</th><th>Distance</th><th>Exemple</th></tr></thead><tbody><tr><td class="vocab-arabic arabic" style="color:var(--success);">هَذَا</td><td style="color:var(--success);">Proche</td><td class="vocab-arabic arabic">هَذَا مَسْجِدٌ</td></tr><tr><td class="vocab-arabic arabic" style="color:var(--accent);">ذَلِكَ</td><td style="color:var(--accent);">Éloigné</td><td class="vocab-arabic arabic">ذَلِكَ بَيْتٌ</td></tr></tbody></table></div></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice pratique</h3><div class="exercise-question"><p>Tu vois une étoile dans le ciel (loin). Comment dis-tu "Cela est une étoile" ?</p></div><div class="options-grid"><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">هَذَا نَجْمٌ</span></button><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">ذَلِكَ نَجْمٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَا نَجْمٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَنْ نَجْمٌ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Vocabulaire supplémentaire</h3><div class="theory-content"><table class="vocab-table"><thead><tr><th>Singulier</th><th>Pluriel</th><th>Traduction</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">إِمَامٌ</td><td class="vocab-arabic arabic">أَئِمَّةٌ</td><td>Imam(s)</td></tr><tr><td class="vocab-arabic arabic">سُكَّرٌ</td><td class="vocab-arabic arabic">-</td><td>Sucre</td></tr><tr><td class="vocab-arabic arabic">حَجَرٌ</td><td class="vocab-arabic arabic">حِجَارٌ</td><td>Pierre(s)</td></tr><tr><td class="vocab-arabic arabic">لَبَنٌ</td><td class="vocab-arabic arabic">أَلْبَانٌ</td><td>Lait(s)</td></tr></tbody></table></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice final</h3><div class="exercise-question"><p>"Ceci est du sucre (proche) et cela est du lait (loin)"</p></div><div class="options-grid"><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">هَذَا سُكَّرٌ وَذَلِكَ لَبَنٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">ذَلِكَ سُكَّرٌ وَهَذَا لَبَنٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">هَذَا سُكَّرٌ وَهَذَا لَبَنٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">ذَلِكَ سُكَّرٌ وَذَلِكَ لَبَنٌ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""}
        ]
    },
    4: {
        "title": "الدرس الرابع - Le défini et l'indéfini",
        "xp": 70,
        "steps": [
            {"type": "theory", "content": """<div class="audio-hint"><span class="audio-hint-icon">🔊</span><span>Clique sur les mots arabes pour entendre leur prononciation !</span></div><div class="theory-section"><h3 class="theory-title">📚 L'indéfini et le défini</h3><div class="theory-content"><div class="grammar-box"><h4>📝 L'indéfini (النَّكِرَة)</h4><ul style="list-style:none;padding:0;"><li>• Base du nom</li><li>• Non désigné</li><li>• Tanwin (ٌ ً ٍ)</li></ul></div><div class="warning-box"><h4>⚠️ Le défini (المَعْرِفَة)</h4><ul style="list-style:none;padding:0;"><li>• Déterminé</li><li>• Article <span class="arabic" style="color:var(--primary);">ال</span></li><li>• Perd le tanwin</li></ul></div><div class="arabic-example"><div class="arabic-word arabic">كِتَابٌ → الكِتَابُ</div><div class="arabic-translation">un livre → le livre</div></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 L'article défini (ال)</h3><div class="theory-content"><p>L'article <span class="arabic" style="font-size:1.5em;color:var(--primary);">ال</span> = ا (hamza de liaison) + ل</p><div class="warning-box"><h4>⚠️ Important</h4><p>La hamza de liaison ne se prononce qu'en <strong>début de phrase</strong> !</p></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Les lettres lunaires 🌙</h3><div class="theory-content"><p>Devant ces lettres, le <strong>لام se prononce</strong> :</p><div class="grammar-box"><h4>📝 Les 14 lettres lunaires</h4><p class="arabic" style="font-size:1.5rem;text-align:center;">أ ب ج ح خ ع غ ف ق ك م و هـ ي</p></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Les lettres solaires ☀️</h3><div class="theory-content"><p>Devant ces lettres, le <strong>لام NE se prononce PAS</strong> :</p><div class="warning-box"><h4>⚠️ Les 14 lettres solaires</h4><p class="arabic" style="font-size:1.5rem;text-align:center;">ت ث د ذ ر ز س ش ص ض ط ظ ل ن</p></div></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice pratique</h3><div class="exercise-question"><p>Dans <span class="arabic" style="font-size:1.5em;">الشَّمْسُ</span>, le لام se prononce-t-il ?</p></div><div class="options-grid"><button class="option-btn" data-correct="false" onclick="checkAnswer(this)">Oui, car ش est lunaire</button><button class="option-btn" data-correct="true" onclick="checkAnswer(this)">Non, car ش est solaire</button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)">Oui, toujours</button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)">Non, jamais</button></div><div class="feedback-message" id="feedback"></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Vocabulaire nouveau</h3><div class="theory-content"><table class="vocab-table"><thead><tr><th>Singulier</th><th>Pluriel</th><th>Traduction</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">مَاءٌ</td><td class="vocab-arabic arabic">مِيَاهٌ</td><td>Eau</td></tr><tr><td class="vocab-arabic arabic">جَدِيدٌ</td><td class="vocab-arabic arabic">جُدُدٌ</td><td>Nouveau</td></tr><tr><td class="vocab-arabic arabic">شَمْسٌ</td><td class="vocab-arabic arabic">شُمُوسٌ</td><td>Soleil</td></tr><tr><td class="vocab-arabic arabic">قَمَرٌ</td><td class="vocab-arabic arabic">أَقْمَارٌ</td><td>Lune</td></tr></tbody></table></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice final</h3><div class="exercise-question"><p>"Le livre est nouveau et la porte est ouverte"</p></div><div class="options-grid"><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">الكِتَابُ جَدِيدٌ وَالبَابُ مَفْتُوحٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">كِتَابٌ جَدِيدٌ وَبَابٌ مَفْتُوحٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">هَذَا كِتَابٌ وَهَذَا بَابٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">الكِتَابُ مَفْتُوحٌ وَالبَابُ جَدِيدٌ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""}
        ]
    },
    5: {
        "title": "الدرس الخامس - Les prépositions (حُرُوفُ الجَرِّ)",
        "xp": 60,
        "steps": [
            {"type": "theory", "content": """<div class="audio-hint"><span class="audio-hint-icon">🔊</span><span>Clique sur les mots arabes pour entendre leur prononciation !</span></div><div class="theory-section"><h3 class="theory-title">📚 Introduction : الإِعْرَابُ (la flexion)</h3><div class="theory-content"><p>En arabe, les terminaisons des mots peuvent <strong>varier</strong>. Cette variation s'appelle <span class="arabic" style="color:var(--primary);font-size:1.3em;">الإِعْرَابُ</span>.</p></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Les prépositions (حُرُوفُ الجَرِّ)</h3><div class="theory-content"><div class="grammar-box"><h4>📝 Le rôle de la préposition</h4><ul style="list-style:none;padding:0;"><li>• Elle agit sur le <strong>sens</strong> d'un nom qui la suit</li><li>• Elle agit sur la <strong>voyelle finale</strong></li><li>• Le nom devient <strong>مَجْرُور</strong> (génitif)</li></ul></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Les principales prépositions</h3><div class="theory-content"><table class="vocab-table"><thead><tr><th>Préposition</th><th>Sens</th><th>Exemple</th></tr></thead><tbody><tr><td class="vocab-arabic arabic" style="font-size:2rem;">فِي</td><td>Dans</td><td class="vocab-arabic arabic">فِي البَيْتِ</td></tr><tr><td class="vocab-arabic arabic" style="font-size:2rem;">عَلَى</td><td>Sur</td><td class="vocab-arabic arabic">عَلَى الطَّاوِلَةِ</td></tr><tr><td class="vocab-arabic arabic" style="font-size:2rem;">مِنْ</td><td>De</td><td class="vocab-arabic arabic">مِنَ المَسْجِدِ</td></tr><tr><td class="vocab-arabic arabic" style="font-size:2rem;">إِلَى</td><td>Vers</td><td class="vocab-arabic arabic">إِلَى المَسْجِدِ</td></tr></tbody></table></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice pratique</h3><div class="exercise-question"><p>Comment dit-on "dans la maison" ?</p></div><div class="options-grid"><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">فِي البَيْتِ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">فِي البَيْتُ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">عَلَى البَيْتِ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مِنَ البَيْتِ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 أَيْنَ - Où ?</h3><div class="theory-content"><div class="arabic-example"><div class="arabic-word arabic">أَيْنَ</div><div class="arabic-translation">Où ?</div></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Vocabulaire : Les lieux</h3><div class="theory-content"><table class="vocab-table"><thead><tr><th>Arabe</th><th>Traduction</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">الغُرْفَةُ</td><td>La chambre</td></tr><tr><td class="vocab-arabic arabic">الحَمَّامُ</td><td>La salle de bain</td></tr><tr><td class="vocab-arabic arabic">المَطْبَخُ</td><td>La cuisine</td></tr><tr><td class="vocab-arabic arabic">المَكْتَبُ</td><td>Le bureau</td></tr></tbody></table></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice final</h3><div class="exercise-question"><p class="arabic" style="font-size:2rem;color:var(--primary);">أَيْنَ الكِتَابُ؟</p><p>Le livre est sur le bureau.</p></div><div class="options-grid"><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">هُوَ عَلَى المَكْتَبِ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">هُوَ فِي المَكْتَبِ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">هُوَ عَلَى المَكْتَبُ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">هُوَ مِنَ المَكْتَبِ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""}
        ]
    },
    6: {
        "title": "الدرس السادس - Les noms propres (العَلَمُ)",
        "xp": 65,
        "steps": [
            {"type": "theory", "content": """<div class="audio-hint"><span class="audio-hint-icon">🔊</span><span>Clique sur les mots arabes pour entendre leur prononciation !</span></div><div class="theory-section"><h3 class="theory-title">📚 Les noms propres (العَلَمُ)</h3><div class="theory-content"><p>Les noms propres sont toujours <strong>définis</strong> (مَعْرِفَة).</p></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Les types de noms définis</h3><div class="theory-content"><div class="grammar-box"><table class="vocab-table"><thead><tr><th>Type</th><th>Exemple</th></tr></thead><tbody><tr><td>Défini par ال</td><td class="vocab-arabic arabic">الكِتَابُ</td></tr><tr><td>Démonstratifs</td><td class="vocab-arabic arabic">هَذَا ، ذَلِكَ</td></tr><tr><td>Noms propres</td><td class="vocab-arabic arabic">مُحَمَّدٌ ، مَكَّةُ</td></tr></tbody></table></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Le tanwin (التَّنْوِينُ)</h3><div class="theory-content"><div class="warning-box"><h4>⚠️ Exception</h4><p>Certains noms n'acceptent pas le tanwin :</p><p class="arabic" style="font-size:1.3rem;text-align:center;">عَائِشَةُ ، فَاطِمَةُ ، مَكَّةُ</p></div></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice pratique</h3><div class="exercise-question"><p>Quel nom propre prend le tanwin ?</p></div><div class="options-grid"><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">مُحَمَّدٌ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">فَاطِمَةُ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">عَائِشَةُ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">مَكَّةُ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 مِنْ أَيْنَ ؟ - D'où ?</h3><div class="theory-content"><div class="arabic-example"><div class="arabic-word arabic">مِنْ أَيْنَ أَنْتَ ؟</div><div class="arabic-translation">D'où viens-tu ?</div></div></div></div>"""},
            {"type": "theory", "content": """<div class="theory-section"><h3 class="theory-title">📚 Vocabulaire : Pays</h3><div class="theory-content"><table class="vocab-table"><thead><tr><th>Arabe</th><th>Français</th></tr></thead><tbody><tr><td class="vocab-arabic arabic">فَرَنْسَا</td><td>France</td></tr><tr><td class="vocab-arabic arabic">اليَابَانُ</td><td>Japon</td></tr><tr><td class="vocab-arabic arabic">الصِّينُ</td><td>Chine</td></tr></tbody></table></div></div>"""},
            {"type": "exercise", "content": """<div class="exercise-section"><h3 class="exercise-title">🎯 Exercice final</h3><div class="exercise-question"><p class="arabic" style="font-size:2rem;color:var(--primary);">مِنْ أَيْنَ أَنْتَ ؟</p><p>Tu viens du Japon.</p></div><div class="options-grid"><button class="option-btn" data-correct="true" onclick="checkAnswer(this)"><span class="arabic">أَنَا مِنَ اليَابَانِ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">أَنَا فِي اليَابَانِ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">أَنَا إِلَى اليَابَانِ</span></button><button class="option-btn" data-correct="false" onclick="checkAnswer(this)"><span class="arabic">أَنَا مِنَ اليَابَانُ</span></button></div><div class="feedback-message" id="feedback"></div></div>"""}
        ]
    }
}


def check_user_has_admin_role(user_id: int) -> bool:
    """
    Vérifie si un utilisateur Discord a le rôle 'admin' (insensible à la casse)

    Returns:
        bool: True si l'utilisateur a un rôle contenant 'admin', False sinon
    """
    try:
        discord_token = os.getenv('DISCORD_TOKEN')
        guild_id = os.getenv('GUILD_ID')

        if not discord_token or not guild_id:
            print("⚠️ DISCORD_TOKEN ou GUILD_ID manquant - impossible de vérifier le rôle admin")
            return False

        # Récupérer les informations du membre via l'API Discord
        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
        headers = {"Authorization": f"Bot {discord_token}"}

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"❌ Erreur API Discord ({response.status_code}): {response.text}")
            return False

        member_data = response.json()
        role_ids = member_data.get('roles', [])

        # Récupérer tous les rôles du serveur
        roles_url = f"https://discord.com/api/v10/guilds/{guild_id}/roles"
        roles_response = requests.get(roles_url, headers=headers)

        if roles_response.status_code != 200:
            print(f"❌ Erreur API Discord roles ({roles_response.status_code})")
            return False

        all_roles = roles_response.json()

        # Vérifier si l'utilisateur a un rôle contenant 'admin' (insensible à la casse)
        for role in all_roles:
            if role['id'] in role_ids and 'admin' in role['name'].lower():
                print(f"✅ Utilisateur {user_id} a le rôle admin: {role['name']}")
                return True

        return False

    except Exception as e:
        print(f"❌ Erreur vérification rôle admin: {e}")
        return False


def find_available_group(niveau: int, db) -> str:
    """
    Trouve le premier groupe disponible pour un niveau donné (< 15 membres)
    Retourne: "1-A", "2-B", etc.
    """
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']

    for letter in letters:
        groupe_name = f"{niveau}-{letter}"

        # Compter combien d'utilisateurs sont dans ce groupe
        count = db.query(func.count(Utilisateur.user_id)).filter(
            Utilisateur.groupe == groupe_name
        ).scalar()

        if count < 15:
            return groupe_name

    # Si tous les groupes A-J sont pleins, retourner K
    return f"{niveau}-K"


def parse_course_content(content):
    """
    Parse la structure complexe du cours en HTML
    """
    html = ""
    
    for section in content:
        # Titre de section
        if 'section_title' in section:
            html += f'<h2 class="section-title">{section["section_title"]}</h2>'
        
        # Items de la section
        if 'items' in section:
            for item in section['items']:
                item_type = item.get('type', '')
                
                if item_type == 'paragraph':
                    html += f'<p>{item["text"]}</p>'
                
                elif item_type == 'heading':
                    html += f'<h3>{item["text"]}</h3>'
                
                elif item_type == 'list':
                    html += '<ul>'
                    for list_item in item['items']:
                        html += f'<li>{list_item}</li>'
                    html += '</ul>'
                
                elif item_type == 'code':
                    html += f'<pre><code>{item["code"]}</code></pre>'
                
                elif item_type == 'example':
                    html += '<div class="example-box">'
                    if 'title' in item:
                        html += f'<h4 class="example-title">{item["title"]}</h4>'
                    if 'text' in item:
                        html += f'<p>{item["text"]}</p>'
                    if 'code' in item:
                        html += f'<pre><code>{item["code"]}</code></pre>'
                    html += '</div>'
    
    return html


@app.route('/')
def index():
    """Page d'accueil"""
    return render_template('home.html')


# ==================== ROUTES COURS D'ARABE ====================

@app.route('/courses', methods=['GET', 'POST'])
def courses():
    """Page d'accès aux cours d'arabe avec filtrage par niveau"""
    if request.method == 'GET':
        return render_template('courses_id.html')

    db = None
    try:
        user_id_str = request.form.get('user_id', '').strip()

        if not user_id_str:
            return render_template('courses_id.html', error="Entre ton ID Discord")

        user_id = int(user_id_str)

        # Chercher l'utilisateur
        db = SessionLocal()
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()

        if not user:
            return render_template('courses_id.html',
                error="Utilisateur non trouve. Utilise /register sur Discord d'abord.")

        # Préparer les infos utilisateur
        user_info = {
            'user_id': user.user_id,
            'username': user.username,
            'niveau_actuel': user.niveau_actuel,
            'groupe': user.groupe
        }

        # Afficher les cours filtrés par niveau
        return render_template('courses_main.html',
            user_info=user_info,
            levels=arabic_courses['levels'])

    except ValueError:
        return render_template('courses_id.html', error="ID Discord invalide")
    except Exception as e:
        print(f"Erreur /courses: {e}")
        return render_template('courses_id.html', error=f"Erreur: {e}")
    finally:
        if db:
            db.close()


@app.route('/courses/lesson/<int:lesson_id>')
def course_lesson(lesson_id):
    """Page d'affichage d'une leçon spécifique"""
    db = None
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return render_template('courses_id.html', error="ID utilisateur manquant")

        user_id = int(user_id)

        # Vérifier l'utilisateur et son niveau
        db = SessionLocal()
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()

        if not user:
            return render_template('courses_id.html', error="Utilisateur non trouve")

        # Déterminer le niveau requis pour cette leçon
        required_level = 1 if lesson_id <= 3 else 2

        if user.niveau_actuel < required_level:
            return render_template('courses_id.html',
                error=f"Tu n'as pas acces a cette lecon. Niveau requis: {required_level}")

        # Récupérer la leçon
        if lesson_id not in LESSONS_DATA:
            return render_template('courses_id.html', error="Lecon introuvable")

        lesson = LESSONS_DATA[lesson_id]

        user_info = {
            'user_id': user.user_id,
            'username': user.username,
            'niveau_actuel': user.niveau_actuel
        }

        return render_template('course_lesson.html',
            lesson_id=lesson_id,
            lesson=lesson,
            user_info=user_info)

    except Exception as e:
        print(f"Erreur /courses/lesson/{lesson_id}: {e}")
        return render_template('courses_id.html', error=f"Erreur: {e}")
    finally:
        if db:
            db.close()


@app.route('/courses/exercises/<int:sheet_id>')
def course_exercises(sheet_id):
    """Page d'exercices pour une fiche donnée"""
    db = None
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return render_template('courses_id.html', error="ID utilisateur manquant")

        user_id = int(user_id)

        # Vérifier l'utilisateur et son niveau
        db = SessionLocal()
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()

        if not user:
            return render_template('courses_id.html', error="Utilisateur non trouve")

        # Vérifier le niveau requis
        if user.niveau_actuel < sheet_id:
            return render_template('courses_id.html',
                error=f"Tu n'as pas acces a cette fiche. Niveau requis: {sheet_id}")

        user_info = {
            'user_id': user.user_id,
            'username': user.username,
            'niveau_actuel': user.niveau_actuel
        }

        return render_template('course_exercises.html',
            sheet_id=sheet_id,
            user_info=user_info)

    except Exception as e:
        print(f"Erreur /courses/exercises/{sheet_id}: {e}")
        return render_template('courses_id.html', error=f"Erreur: {e}")
    finally:
        if db:
            db.close()


@app.route('/exam_secure')
def exam_secure():
    """Page d'examen sécurisée avec anti-triche"""
    user_id = request.args.get('user_id')
    exam_id = request.args.get('exam_id')
    
    if not user_id or not exam_id:
        return "Paramètres manquants", 400
    
    return render_template('exam_secure.html')


@app.route('/api/get_exam/<int:exam_id>')
def api_get_exam(exam_id):
    """API pour récupérer les données d'un examen"""
    try:
        # Chercher l'examen dans exam.json
        exam = None
        for e in exams_data:
            if e['id'] == exam_id:
                exam = e
                break
        
        if not exam:
            return jsonify({'error': 'Examen introuvable'}), 404
        
        return jsonify(exam)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/submit_exam', methods=['POST'])
def api_submit_exam():
    """API pour soumettre un examen"""
    try:
        data = request.json
        user_id = data.get('user_id')
        exam_id = data.get('exam_id')
        answers = data.get('answers')
        
        if not user_id or not exam_id or answers is None:
            return jsonify({'error': 'Données manquantes'}), 400
        
        # Charger l'examen
        exam = None
        for e in exams_data:
            if e['id'] == exam_id:
                exam = e
                break
        
        if not exam:
            return jsonify({'error': 'Examen introuvable'}), 404
        
        # Calculer le score
        score = 0
        total = len(exam['questions'])
        results = []
        
        for i, question in enumerate(exam['questions']):
            user_answer = answers[i]
            correct_answer = question['correct']
            is_correct = user_answer == correct_answer
            
            if is_correct:
                score += 1
            
            results.append({
                'question': i + 1,
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct
            })
        
        percentage = (score / total) * 100
        passing_score = exam.get('passing_score', 80)
        passed = percentage >= passing_score
        
        # Sauvegarder en DB
        db = SessionLocal()
        try:
            # Vérifier si l'utilisateur existe
            user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
            
            if not user:
                return jsonify({'error': 'Utilisateur introuvable'}), 404
            
            # Créer le résultat
            exam_result = ExamResult(
                user_id=user_id,
                exam_id=exam_id,
                exam_title=exam['title'],
                score=score,
                total=total,
                percentage=percentage,
                passed=passed,
                passing_score=passing_score,
                date=datetime.now(),
                notified=False,
                results=results
            )
            
            db.add(exam_result)
            
            # Si réussi, promouvoir
            if passed:
                old_niveau = user.niveau_actuel
                user.niveau_actuel += 1
                user.examens_reussis += 1
                
                # Calculer le nouveau groupe
                new_groupe = f"{user.niveau_actuel}-{user.groupe.split('-')[1]}"
                user.groupe = new_groupe
            
            db.commit()
            
            return jsonify({
                'success': True,
                'score': score,
                'total': total,
                'percentage': percentage,
                'passed': passed
            })
        
        finally:
            db.close()
    
    except Exception as e:
        print(f"Erreur submit_exam: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/exams', methods=['GET', 'POST'])
def exams():
    """Page d'examens avec vérification du vote"""
    if request.method == 'GET':
        # Vérifier si l'utilisateur a une session active
        if 'user_id' in session and 'exam_period_id' in session:
            # Rediriger vers POST pour traiter la session
            db = SessionLocal()
            try:
                user_id = session['user_id']
                user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
                now = datetime.utcnow()

                if user:
                    # Vérifier si la période d'examen est toujours active
                    exam_period = db.query(ExamPeriod).filter(
                        ExamPeriod.id == session['exam_period_id'],
                        ExamPeriod.start_time <= now,
                        ExamPeriod.end_time >= now
                    ).first()

                    if exam_period:
                        # Trouver l'examen
                        exam = None
                        for e in exams_data['exams']:
                            if e['group'] == user.niveau_actuel:
                                exam = e
                                break

                        if exam:
                            # Retourner directement à l'examen
                            return render_template('exam_secure.html',
                                exam=exam,
                                user_id=user_id,
                                exam_period=exam_period,
                                user_info={
                                    'username': user.username,
                                    'niveau_actuel': user.niveau_actuel,
                                    'groupe': user.groupe
                                })
                    else:
                        # Période expirée, nettoyer la session
                        session.clear()
            finally:
                db.close()

        return render_template('exams_id.html')
    
    db = None
    try:
        user_id_str = request.form.get('user_id', '').strip()
        
        if not user_id_str:
            return render_template('exams_id.html', error="Entre ton ID Discord")
        
        user_id = int(user_id_str)
        
        # 1. Chercher l'utilisateur
        db = SessionLocal()
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()

        if not user:
            return render_template('exams_id.html',
                error="Utilisateur non trouvé. Utilise /register sur Discord d'abord.")

        # 2. Vérifier période d'examen active (AVANT de vérifier si déjà passé)
        now = datetime.utcnow()  # Utiliser UTC pour cohérence avec la DB

        # Debug : afficher l'heure actuelle
        print(f"🕐 Heure serveur (UTC): {now.strftime('%d/%m/%Y %H:%M:%S')}")

        exam_period = db.query(ExamPeriod).filter(
            ExamPeriod.group_number == user.niveau_actuel,
            ExamPeriod.start_time <= now,
            ExamPeriod.end_time >= now
        ).first()

        # Debug : afficher les périodes trouvées
        all_periods = db.query(ExamPeriod).filter(
            ExamPeriod.group_number == user.niveau_actuel
        ).all()
        for p in all_periods:
            print(f"📅 Période trouvée - Début: {p.start_time}, Fin: {p.end_time}, Active: {p.start_time <= now <= p.end_time}")

        if not exam_period:
            # Chercher la prochaine période d'examen
            next_period = db.query(ExamPeriod).filter(
                ExamPeriod.group_number == user.niveau_actuel,
                ExamPeriod.start_time > now
            ).order_by(ExamPeriod.start_time).first()

            if next_period:
                # Calculer le temps restant jusqu'au début
                seconds_remaining = int((next_period.start_time - now).total_seconds())
                total_seconds = int((next_period.start_time - (next_period.start_time - timedelta(days=7))).total_seconds())

                # Calculer le pourcentage de progression (compte à rebours)
                progress = max(0, min(100, int((seconds_remaining / total_seconds) * 100)))

                # Message adapté selon la proximité
                if seconds_remaining < 3600:  # Moins d'1h
                    message = "🔥 PRÉPARE-TOI BIEN SOLDAT, TON EXAMEN APPROCHE !"
                    title = "⚔️ AU COMBAT DANS MOINS D'1H"
                elif seconds_remaining < 86400:  # Moins d'1j
                    message = "💪 L'HEURE DE LA BATAILLE APPROCHE, RÉVISE BIEN !"
                    title = "🎯 EXAMEN IMMINENT"
                elif seconds_remaining < 259200:  # Moins de 3j
                    message = "📚 IL EST TEMPS DE RÉVISER SÉRIEUSEMENT"
                    title = "📖 PRÉPARATION EN COURS"
                else:
                    message = "😌 PROFITE DE CE TEMPS POUR BIEN TE PRÉPARER"
                    title = "⏳ EXAMEN PROGRAMMÉ"

                # Calculer le countdown
                days = seconds_remaining // 86400
                hours = (seconds_remaining % 86400) // 3600
                minutes = (seconds_remaining % 3600) // 60
                seconds = seconds_remaining % 60

                time_text = ''
                if days > 0:
                    time_text += f"{days}J "
                if hours > 0:
                    time_text += f"{hours}H "
                if minutes > 0:
                    time_text += f"{minutes}M "
                time_text += f"{seconds}S"

                # Vérifier le statut de vote
                valid_vote = (
                    user.has_voted and
                    (user.current_exam_period == next_period.id or user.current_exam_period == "test")
                )

                return render_template('exam_waiting.html',
                    title=title,
                    message=message,
                    time_text=time_text,
                    progress=progress,
                    seconds_remaining=seconds_remaining,
                    total_seconds=total_seconds,
                    is_full=False,
                    has_voted=valid_vote,
                    exam_period_id=next_period.id,
                    user_id=user_id)
            else:
                # Pas d'exam programmé → Barre 100HP "repose-toi"
                return render_template('exam_waiting.html',
                    title='',
                    message='😌 REPOSE-TOI BIEN TANT QU\'IL EN EST ENCORE TEMPS...',
                    time_text='',
                    progress=100,
                    seconds_remaining=0,
                    total_seconds=1,
                    is_full=True)

        # 3. Vérifier si l'utilisateur a déjà passé l'examen PENDANT CETTE PÉRIODE
        # Trouver l'examen correspondant au niveau
        exam = None
        for e in exams_data['exams']:
            if e['group'] == user.niveau_actuel:
                exam = e
                break

        if exam:
            # Vérifier s'il existe déjà un résultat pour cet examen PENDANT cette période
            existing_result = db.query(ExamResult).filter(
                ExamResult.user_id == user_id,
                ExamResult.exam_id == exam['id'],
                ExamResult.date >= exam_period.start_time,
                ExamResult.date <= exam_period.end_time
            ).first()

            if existing_result:
                # L'utilisateur a déjà passé cet examen pendant cette période
                # Vérifier s'il a le rôle admin
                is_admin = check_user_has_admin_role(user_id)

                if not is_admin:
                    # Pas admin et déjà passé pour cette période → BLOQUER
                    return render_template('exams_id.html',
                        error=f"⚠️ Tu as déjà passé l'examen pour cette période !\n\n"
                              f"📊 Résultat: {existing_result.percentage}% ({existing_result.score}/{existing_result.total} points)\n"
                              f"{'✅ Réussi' if existing_result.passed else '❌ Échoué'}\n\n"
                              f"Tu ne peux passer l'examen qu'une seule fois par période.\n"
                              f"Attends la prochaine période d'examen.")
                else:
                    print(f"🔑 Admin détecté - {user.username} peut repasser l'examen")

        # 4. Vérifier que l'utilisateur a voté
        # Pour les tests, accepter "test" comme exam_period valide
        valid_vote = (
            user.has_voted and
            (user.current_exam_period == exam_period.id or user.current_exam_period == "test")
        )

        if not valid_vote:
            return render_template('exams_id.html',
                error=f"⚠️ Tu dois voter avant de passer l'examen !\n\n"
                      f"Utilise la commande Discord :\n"
                      f"/vote @user1")

        # 5. Vérifier qu'on a bien trouvé un examen (normalement déjà fait plus haut)
        if not exam:
            return render_template('exams_id.html',
                error=f"Aucun examen pour le niveau {user.niveau_actuel}")

        # 6. Stocker dans la session pour permettre le retour
        session['user_id'] = user_id
        session['exam_period_id'] = exam_period.id

        # 7. Afficher l'examen sécurisé avec la période d'examen
        return render_template('exam_secure.html',
            exam=exam,
            user_id=user_id,
            exam_period=exam_period,
            user_info={
                'username': user.username,
                'niveau_actuel': user.niveau_actuel,
                'groupe': user.groupe
            })
    
    except Exception as e:
        return render_template('exams_id.html', error=f"Erreur: {e}")
    
    finally:
        if db:
            db.close()

@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    """
    Soumet un examen
    SI RÉUSSI (≥70%) → PROMOUVOIR automatiquement
    """
    db = None
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        exam_id = int(data['exam_id'])
        answers = data['answers']
        
        # Trouver l'examen
        exam = None
        for e in exams_data['exams']:
            if e['id'] == exam_id:
                exam = e
                break
        
        if not exam:
            return jsonify({'success': False, 'message': 'Examen introuvable'}), 404
        
        # Calculer le score
        score = 0
        total_points = 0
        results = []
        
        for question in exam['questions']:
            q_id = question['id']
            user_answer = answers.get(str(q_id))

            # Utiliser le système de validation des exercices
            correct = exercise_types.validate_question(question, user_answer)

            points = question.get('points', 1)
            total_points += points

            if correct:
                score += points

            # Déterminer la réponse correcte à afficher (selon le type)
            q_type = question.get('type', 'qcm')
            if q_type == 'matching':
                correct_answer = "Voir paires correctes"
            elif q_type in ['text_input', 'translation']:
                correct_answer = question.get('accept', [question.get('correct', question.get('correct_ar', ''))])
            elif q_type == 'word_order':
                correct_answer = ' '.join(question.get('correct_order', []))
            else:
                correct_answer = question.get('correct', '')

            results.append({
                'question_id': q_id,
                'question_text': question['text'],
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': correct,
                'points': points
            })
        
        percentage = round((score / total_points) * 100, 2)
        passed = percentage >= exam.get('passing_score', 70)
        
        print(f"\n{'='*50}")
        print(f"📊 RÉSULTAT EXAMEN")
        print(f"   User: {user_id}")
        print(f"   Score: {percentage}%")
        print(f"   Statut: {'✅ RÉUSSI' if passed else '❌ ÉCHOUÉ'}")
        
        # Sauvegarder le résultat
        db = SessionLocal()
        
        exam_result = ExamResult(
            user_id=user_id,
            exam_id=exam_id,
            exam_title=exam['title'],
            score=score,
            total=total_points,
            percentage=percentage,
            passed=passed,
            passing_score=exam.get('passing_score', 70),
            date=datetime.now(),
            notified=False,
            results=results
        )
        
        db.add(exam_result)
        db.commit()
        print(f"✅ Résultat sauvegardé en base")

        # Utiliser GroupManager pour gérer la suite
        group_manager = GroupManager(db)
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()

        if not user:
            print(f"⚠️ Utilisateur {user_id} introuvable")
        else:
            # SI RÉUSSI → PROMOUVOIR
            if passed:
                if user.niveau_actuel < 5:
                    old_groupe, new_groupe = group_manager.promote_user(user_id)

                    print(f"🎉 PROMOTION EN BASE DE DONNÉES")
                    print(f"   {old_groupe} → {new_groupe}")
                    print(f"✅ Utilisateur promu en base")

                    if new_groupe == "Alumni":
                        print(f"🎓 {user.username} a terminé la formation ! (Alumni)")
                    elif "Waiting List" in new_groupe:
                        print(f"📋 {user.username} en waiting list pour le niveau {user.niveau_actuel}")
                    else:
                        print(f"💡 Utilise /actualiser_exams sur Discord pour appliquer les changements")
                elif user.niveau_actuel == 5:
                    # Niveau 5 terminé → Alumni
                    user.is_alumni = True
                    user.examens_reussis = 5
                    db.commit()
                    print(f"🎓 {user.username} a terminé le niveau 5 → Alumni !")

            # SI ÉCHOUÉ → SYSTÈME DE RATTRAPAGE
            else:
                old_groupe = user.groupe
                niveau = user.niveau_actuel

                result_info = group_manager.handle_exam_failure(user_id, niveau, percentage)

                print(f"❌ ÉCHEC - Système de rattrapage activé")
                print(f"   Note: {percentage}% (Catégorie: {result_info['categorie']})")
                print(f"   Action: {result_info['action']}")

                if result_info['action'] == 'rattrapage':
                    print(f"   Groupe: {result_info['groupe']}")
                    print(f"   Délai: {result_info['delai_jours']} jours")
                    print(f"   Examen: {result_info['date_exam'].strftime('%Y-%m-%d %H:%M')}")
                elif result_info['action'] == 'assign_group':
                    print(f"   Assigné au groupe: {result_info['groupe']}")
                elif result_info['action'] == 'waiting_list':
                    print(f"   En waiting list: {result_info['raison']}")

                print(f"💡 Utilise /actualiser_exams sur Discord pour appliquer les changements")

        print(f"{'='*50}\n")

        # Nettoyer la session une fois l'examen soumis
        session.clear()

        return jsonify({
            'success': True,
            'score': score,
            'total': total_points,
            'percentage': percentage,
            'passed': passed,
            'passing_score': exam.get('passing_score', 70)
        })
    
    except Exception as e:
        print(f"❌ Erreur submit_exam: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    
    finally:
        if db:
            db.close()


@app.route('/api/debug/users')
def debug_users():
    """DEBUG : Liste tous les utilisateurs"""
    db = None
    try:
        db = SessionLocal()
        users = db.query(Utilisateur).all()
        
        users_list = []
        for user in users:
            users_list.append({
                'user_id': user.user_id,
                'username': user.username,
                'niveau_actuel': user.niveau_actuel,
                'groupe': user.groupe,
                'cohorte_id': user.cohorte_id
            })
        
        return jsonify({
            'total': len(users_list),
            'users': users_list
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        if db:
            db.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
