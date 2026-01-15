"""
Application Web Flask - Système de Formation Python
Gestion des examens en ligne
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
from datetime import datetime
import os

# Import des modèles et connexion DB
from db_connection import SessionLocal
from models import Utilisateur, ExamResult

app = Flask(__name__)
app.secret_key = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2'

# Charger les examens
with open('exam.json', 'r', encoding='utf-8') as f:
    exams_data = json.load(f)


@app.route('/')
def index():
    """Page d'accueil"""
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Formation Python</title>
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #fff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                text-align: center;
            }
            .container {
                max-width: 600px;
                padding: 3rem;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            h1 { 
                font-size: 3rem;
                margin-bottom: 1rem;
            }
            p { 
                font-size: 1.2rem;
                line-height: 1.8;
                margin: 1rem 0;
                opacity: 0.9;
            }
            .btn {
                display: inline-block;
                margin-top: 2rem;
                padding: 1rem 3rem;
                background: #fff;
                color: #667eea;
                text-decoration: none;
                border-radius: 50px;
                font-weight: bold;
                font-size: 1.1rem;
                transition: all 0.3s;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            }
            .btn:hover {
                transform: translateY(-3px);
                box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 Formation Python</h1>
            <p>Plateforme d'apprentissage et d'évaluation</p>
            <p>Connectez-vous via Discord pour accéder aux cours</p>
            <a href="/exams" class="btn">📝 Accéder aux Examens</a>
        </div>
    </body>
    </html>
    """


@app.route('/exams', methods=['GET', 'POST'])
def exams():
    """
    Page d'accès aux examens
    GET : Formulaire de saisie ID Discord
    POST : Affiche l'examen disponible
    """
    if request.method == 'GET':
        return render_template('exams.html')
    
    # POST - Traitement de la soumission du formulaire
    db = None
    try:
        user_id_str = request.form.get('user_id', '').strip()
        
        if not user_id_str:
            return render_template('exams.html', error="Veuillez entrer votre ID Discord")
        
        # Valider que c'est bien un nombre
        try:
            user_id = int(user_id_str)
        except ValueError:
            return render_template('exams.html', error="ID Discord invalide (doit être composé de chiffres uniquement)")
        
        # Connexion à PostgreSQL
        db = SessionLocal()
        
        # 1. CHERCHER l'utilisateur dans la base
        user = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
        
        if not user:
            # ❌ Utilisateur non trouvé
            print(f"❌ Utilisateur {user_id} non trouvé dans PostgreSQL")
            return render_template('exams.html', 
                error="Utilisateur non trouvé. Assurez-vous d'avoir rejoint le serveur Discord et utilisé la commande /register si nécessaire.")
        
        # ✅ Utilisateur trouvé !
        print(f"✅ Utilisateur trouvé : {user.username} (Niveau {user.niveau_actuel}, Groupe {user.groupe})")
        
        # 2. Récupérer le niveau actuel
        niveau_actuel = user.niveau_actuel
        
        # 3. Trouver l'examen correspondant au niveau
        exam = None
        for e in exams_data['exams']:
            if e['group'] == niveau_actuel:
                exam = e
                break
        
        if not exam:
            print(f"❌ Aucun examen trouvé pour le niveau {niveau_actuel}")
            return render_template('exams.html', 
                error=f"Aucun examen disponible pour le niveau {niveau_actuel}. Contactez un administrateur.")
        
        print(f"✅ Examen trouvé : {exam['title']} (ID: {exam['id']})")
        
        # 4. Vérifier les dates de disponibilité (si définies)
        now = datetime.now()
        
        # Vérifier si les dates existent
        if 'start_date' in exam and 'end_date' in exam:
            try:
                exam_start = datetime.fromisoformat(exam['start_date'])
                exam_end = datetime.fromisoformat(exam['end_date'])
                
                # Vérifier si l'examen est ouvert
                if now < exam_start:
                    return render_template('exams.html', 
                        error=f"L'examen du niveau {niveau_actuel} n'est pas encore ouvert. Ouverture prévue le {exam_start.strftime('%d/%m/%Y à %H:%M')}")
                
                if now > exam_end:
                    return render_template('exams.html', 
                        error=f"L'examen du niveau {niveau_actuel} est terminé. Il s'est clôturé le {exam_end.strftime('%d/%m/%Y à %H:%M')}")
            
            except (ValueError, TypeError) as date_error:
                print(f"⚠️ Erreur de parsing des dates : {date_error}")
                # Si erreur de dates, on continue quand même (examen toujours disponible)
        
        # 5. Tout est OK, afficher l'examen
        print(f"✅ Affichage de l'examen pour {user.username}")
        
        return render_template('exam_take.html', 
            exam=exam,
            user_id=user_id,
            user_info={
                'username': user.username,
                'niveau_actuel': user.niveau_actuel,
                'groupe': user.groupe
            })
    
    except Exception as e:
        print(f"❌ ERREUR /exams: {e}")
        import traceback
        traceback.print_exc()
        return render_template('exams.html', error=f"Erreur serveur: {str(e)}")
    
    finally:
        # Toujours fermer la connexion DB
        if db:
            db.close()


@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    """Soumet et corrige un examen"""
    db = None
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        exam_id = int(data['exam_id'])
        answers = data['answers']
        
        print(f"📝 Soumission examen : User {user_id}, Exam {exam_id}")
        
        # Trouver l'examen
        exam = None
        for e in exams_data['exams']:
            if e['id'] == exam_id:
                exam = e
                break
        
        if not exam:
            print(f"❌ Examen {exam_id} introuvable")
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
        
        print(f"📊 Score calculé : {score}/{total_points} = {percentage}% - {'✅ Réussi' if passed else '❌ Échoué'}")
        
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
        
        print(f"✅ Résultat sauvegardé dans PostgreSQL (notified=False)")
        
        return jsonify({
            'success': True,
            'score': score,
            'total': total_points,
            'percentage': percentage,
            'passed': passed,
            'passing_score': exam.get('passing_score', 70)
        })
    
    except Exception as e:
        print(f"❌ ERREUR submit_exam: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    
    finally:
        # Toujours fermer la connexion DB
        if db:
            db.close()


@app.route('/api/health')
def health():
    """Endpoint de vérification de santé"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/debug/users')
def debug_users():
    """DEBUG : Affiche tous les utilisateurs (à supprimer en production)"""
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
