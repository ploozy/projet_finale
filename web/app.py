"""
Site Web - Version Finale
1. Entre ton ID → Affiche TON examen automatiquement
2. Promotion automatique après réussite
"""

from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime
import os
from db_connection import SessionLocal
from models import Utilisateur, ExamResult

app = Flask(__name__)
app.secret_key = 'secret'

# Charger les examens
with open('exam.json', 'r', encoding='utf-8') as f:
    exams_data = json.load(f)


@app.route('/')
def index():
    """Page d'accueil"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Formation Python</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                padding: 50px;
            }
            a {
                display: inline-block;
                margin: 10px;
                padding: 15px 30px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 25px;
                font-weight: bold;
                transition: all 0.3s;
            }
            a:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(255,255,255,0.3);
            }
        </style>
    </head>
    <body>
        <h1>🎓 Formation Python</h1>
        <p>Plateforme d'examens et de cours en ligne</p>
        <a href="/courses">📚 Voir les Cours</a>
        <a href="/exams">📝 Accéder aux Examens</a>
    </body>
    </html>
    """


@app.route('/courses')
def courses():
    """Page d'affichage des cours"""
    # Charger les cours depuis course_content.json
    try:
        with open('course_content.json', 'r', encoding='utf-8') as f:
            courses_data = json.load(f)
        
        # Formater le contenu HTML
        for course in courses_data['courses']:
            # Convertir le contenu texte en HTML
            content_html = course['content'].replace('\n\n', '</p><p>')
            content_html = f'<p>{content_html}</p>'
            
            # Remplacer les blocs de code
            import re
            code_blocks = re.findall(r'```python\n(.*?)\n```', course['content'], re.DOTALL)
            for code in code_blocks:
                content_html = content_html.replace(
                    f'```python\n{code}\n```',
                    f'<pre><code>{code}</code></pre>'
                )
            
            course['content'] = content_html
        
        return render_template('courses.html', courses=courses_data['courses'])
    
    except FileNotFoundError:
        return "Fichier course_content.json introuvable", 404


@app.route('/course/<course_id>')
def course_detail(course_id):
    """Page d'affichage d'un cours spécifique"""
    try:
        with open('course_content.json', 'r', encoding='utf-8') as f:
            courses_data = json.load(f)
        
        # Trouver le cours
        course = None
        for c in courses_data['courses']:
            if c['id'] == course_id:
                course = c
                break
        
        if not course:
            return f"Cours '{course_id}' introuvable", 404
        
        # Formater le contenu HTML
        content_html = course['content'].replace('\n\n', '</p><p>')
        content_html = f'<p>{content_html}</p>'
        
        # Remplacer les blocs de code
        import re
        code_blocks = re.findall(r'```python\n(.*?)\n```', course['content'], re.DOTALL)
        for code in code_blocks:
            content_html = content_html.replace(
                f'```python\n{code}\n```',
                f'<pre><code>{code}</code></pre>'
            )
        
        course['content'] = content_html
        
        return render_template('course_detail.html', course=course)
    
    except FileNotFoundError:
        return "Fichier course_content.json introuvable", 404


@app.route('/exams', methods=['GET', 'POST'])
def exams():
    """
    Page d'examens
    1. Entre ton ID
    2. Affiche automatiquement TON examen (filtré par niveau)
    """
    if request.method == 'GET':
        return render_template('exams_id.html')
    
    # POST - L'utilisateur a entré son ID
    db = None
    try:
        user_id_str = request.form.get('user_id', '').strip()
        
        if not user_id_str:
            return render_template('exams_id.html', 
                error="Entre ton ID Discord")
        
        user_id = int(user_id_str)
        
        print(f"\n{'='*50}")
        print(f"📝 Demande d'examen : User {user_id}")
        
        # 1. Chercher l'utilisateur
        db = SessionLocal()
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
        
        if not user:
            print(f"❌ Utilisateur {user_id} non trouvé")
            return render_template('exams_id.html',
                error="Utilisateur non trouvé. Utilise /register sur Discord d'abord.")
        
        print(f"✅ Utilisateur : {user.username}")
        print(f"   Niveau: {user.niveau_actuel}")
        print(f"   Groupe: {user.groupe}")
        
        # 2. Trouver l'examen de SON niveau
        exam = None
        for e in exams_data['exams']:
            if e['group'] == user.niveau_actuel:
                exam = e
                break
        
        if not exam:
            return render_template('exams_id.html',
                error=f"Aucun examen pour le niveau {user.niveau_actuel}")
        
        print(f"✅ Examen : {exam['title']}")
        print(f"{'='*50}\n")
        
        # 3. Afficher l'examen
        return render_template('exam_take.html',
            exam=exam,
            user_id=user_id,
            user_info={
                'username': user.username,
                'niveau_actuel': user.niveau_actuel,
                'groupe': user.groupe
            })
    
    except Exception as e:
        print(f"❌ Erreur /exams: {e}")
        import traceback
        traceback.print_exc()
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
            correct = user_answer == question['correct']
            points = question.get('points', 1)
            total_points += points
            
            if correct:
                score += points
            
            results.append({
                'question_id': q_id,
                'question_text': question['text'],
                'user_answer': user_answer,
                'correct_answer': question['correct'],
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
        
        # SI RÉUSSI → PROMOUVOIR
        if passed:
            user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
            
            if user and user.niveau_actuel < 5:
                old_niveau = user.niveau_actuel
                old_groupe = user.groupe
                
                # Nouveau niveau et groupe
                new_niveau = old_niveau + 1
                new_groupe = f"{new_niveau}-A"  # Toujours mettre dans le groupe A du niveau suivant
                
                user.niveau_actuel = new_niveau
                user.groupe = new_groupe
                user.examens_reussis += 1
                db.commit()
                
                print(f"🎉 PROMOTION AUTOMATIQUE")
                print(f"   {old_groupe} (Niveau {old_niveau}) → {new_groupe} (Niveau {new_niveau})")
                print(f"✅ Utilisateur promu en base")
        
        print(f"{'='*50}\n")
        
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
