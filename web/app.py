"""
Site Web - Version Simplifiée
Affiche TOUS les examens, l'utilisateur choisit le sien
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
                margin-top: 20px;
                padding: 15px 30px;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 25px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <h1>🎓 Formation Python</h1>
        <p>Plateforme d'examens en ligne</p>
        <a href="/exams">📝 Accéder aux Examens</a>
    </body>
    </html>
    """


@app.route('/exams', methods=['GET', 'POST'])
def exams():
    """
    Page d'examens - AFFICHE TOUS LES EXAMENS
    L'utilisateur choisit manuellement le sien
    """
    if request.method == 'GET':
        # Afficher le formulaire
        return render_template('exams.html', exams=exams_data['exams'])
    
    # POST - L'utilisateur a choisi un examen
    try:
        user_id_str = request.form.get('user_id', '').strip()
        exam_id_str = request.form.get('exam_id', '').strip()
        
        if not user_id_str or not exam_id_str:
            return render_template('exams.html', 
                exams=exams_data['exams'],
                error="Entre ton ID Discord et choisis un examen")
        
        user_id = int(user_id_str)
        exam_id = int(exam_id_str)
        
        print(f"\n{'='*50}")
        print(f"📝 Tentative d'examen")
        print(f"   User ID: {user_id}")
        print(f"   Exam ID: {exam_id}")
        
        # 1. Chercher l'utilisateur
        db = SessionLocal()
        try:
            user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
            
            if not user:
                print(f"❌ Utilisateur {user_id} non trouvé en base")
                return render_template('exams.html',
                    exams=exams_data['exams'],
                    error="Utilisateur non trouvé. Utilise /register sur Discord d'abord.")
            
            print(f"✅ Utilisateur trouvé : {user.username}")
            print(f"   Niveau: {user.niveau_actuel}")
            print(f"   Groupe: {user.groupe}")
            
            # 2. Trouver l'examen
            exam = None
            for e in exams_data['exams']:
                if e['id'] == exam_id:
                    exam = e
                    break
            
            if not exam:
                return render_template('exams.html',
                    exams=exams_data['exams'],
                    error="Examen introuvable")
            
            print(f"✅ Examen trouvé : {exam['title']} (Groupe {exam['group']})")
            
            # 3. Vérifier que c'est le bon niveau
            if exam['group'] != user.niveau_actuel:
                print(f"❌ Mauvais niveau : User={user.niveau_actuel}, Exam={exam['group']}")
                return render_template('exams.html',
                    exams=exams_data['exams'],
                    error=f"❌ Cet examen est pour le Niveau {exam['group']}, tu es Niveau {user.niveau_actuel}")
            
            print(f"✅ Niveau correct !")
            print(f"{'='*50}\n")
            
            # 4. Afficher l'examen
            return render_template('exam_take.html',
                exam=exam,
                user_id=user_id,
                user_info={
                    'username': user.username,
                    'niveau_actuel': user.niveau_actuel,
                    'groupe': user.groupe
                })
        
        finally:
            db.close()
    
    except Exception as e:
        print(f"❌ Erreur /exams: {e}")
        import traceback
        traceback.print_exc()
        return render_template('exams.html',
            exams=exams_data['exams'],
            error=f"Erreur: {e}")


@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    """Soumet un examen"""
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
        
        print(f"📊 Résultat : User {user_id}, Score {percentage}%, {'✅ Réussi' if passed else '❌ Échoué'}")
        
        # Sauvegarder dans PostgreSQL
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
