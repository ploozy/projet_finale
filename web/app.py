from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
from datetime import datetime
import os

# ✅ UTILISATION DE POSTGRESQL
from cohorte_manager_sql import CohortManagerSQL
from exam_result_database_sql import ExamResultDatabaseSQL

app = Flask(__name__)
app.secret_key = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2'

# Initialisation des managers SQL
cohort_manager = CohortManagerSQL()
exam_db = ExamResultDatabaseSQL()

# Charger les cours
with open('courses_content.json', 'r', encoding='utf-8') as f:
    courses_content = json.load(f)

# Charger les examens
with open('exam.json', 'r', encoding='utf-8') as f:
    exams_data = json.load(f)


@app.route('/')
def index():
    """Page d'accueil - Redirection vers Discord"""
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Plateforme de Formation</title>
        <style>
            body {
                background: #0d1117;
                color: #c9d1d9;
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
                background: #161b22;
                border-radius: 10px;
                border: 1px solid #30363d;
            }
            h1 { color: #ff8c00; margin-bottom: 1.5rem; }
            p { font-size: 1.2rem; line-height: 1.8; margin: 1rem 0; }
            code {
                background: #0d1117;
                padding: 0.3rem 0.6rem;
                border-radius: 5px;
                color: #ff8c00;
                font-size: 1.1rem;
            }
            .btn {
                display: inline-block;
                margin-top: 1.5rem;
                padding: 0.8rem 2rem;
                background: #ff8c00;
                color: #fff;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: background 0.3s;
            }
            .btn:hover {
                background: #ff7700;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 Plateforme de Formation</h1>
            <p>Pour accéder aux cours, rejoignez notre serveur Discord.</p>
            <p>Contactez un administrateur pour être inscrit via :</p>
            <p><code>/send_course [numéro] @vous</code></p>
            <a href="/exams" class="btn">📝 Passer un examen</a>
        </div>
    </body>
    </html>
    """


@app.route('/course/<int:course_id>')
def course_detail(course_id):
    """Page détaillée d'un cours"""
    course = next((c for c in courses_content['courses'] if c['id'] == course_id), None)
    if not course:
        return "Cours introuvable", 404
    
    return render_template('course_detail.html', course=course)


@app.route('/exams', methods=['GET', 'POST'])
def exams():
    """
    ✅ SYSTÈME D'EXAMEN AVEC INSCRIPTION AUTOMATIQUE
    GET : Formulaire de saisie ID Discord
    POST : Inscrit automatiquement l'utilisateur et affiche l'examen
    """
    if request.method == 'GET':
        return render_template('exams.html')
    
    # POST - Vérification et affichage de l'examen
    try:
        user_id = int(request.form.get('user_id'))
        username = request.form.get('username', f'User_{user_id}')
        
        # 1. Vérifier si l'utilisateur existe, sinon l'inscrire automatiquement
        user_info = cohort_manager.get_user_info(user_id)
        
        if not user_info:
            # Inscription automatique niveau 1
            cohorte_id, niveau = cohort_manager.add_user_to_cohort(user_id, username)
            user_info = cohort_manager.get_user_info(user_id)
            print(f"✅ Nouvel utilisateur inscrit : {username} dans {cohorte_id}")
        
        # 2. Récupérer le niveau de l'utilisateur
        niveau = user_info['niveau_actuel']
        
        # 3. Trouver l'examen correspondant au niveau (group)
        exam = next((e for e in exams_data['exams'] if e['group'] == niveau), None)
        
        if not exam:
            return render_template('exams.html', error=f"Aucun examen disponible pour le niveau {niveau}")
        
        # 4. Vérifier la tranche horaire de l'examen
        now = datetime.now()
        exam_start = datetime.fromisoformat(exam['start_date'])
        exam_end = datetime.fromisoformat(exam['end_date'])
        
        if now < exam_start:
            return render_template('exams.html', 
                error=f"L'examen du niveau {niveau} n'est pas encore ouvert.\nOuverture le {exam_start.strftime('%d/%m/%Y à %H:%M')}")
        
        if now > exam_end:
            return render_template('exams.html', 
                error=f"L'examen du niveau {niveau} est terminé.\nIl s'est clôturé le {exam_end.strftime('%d/%m/%Y à %H:%M')}")
        
        # 5. Vérifier si l'utilisateur n'a pas déjà passé cet examen aujourd'hui
        user_results = exam_db.get_user_exam_results(user_id)
        today = datetime.now().date()
        
        for result in user_results:
            result_date = datetime.fromisoformat(result['date']).date()
            if result['exam_id'] == exam['id'] and result_date == today:
                return render_template('exams.html', 
                    error=f"Vous avez déjà passé cet examen aujourd'hui.\nScore: {result['score']}/{result['total']} ({result['percentage']}%)")
        
        # 6. Afficher l'examen
        return render_template('exam_take.html', 
                             exam=exam, 
                             user_id=user_id,
                             user_info=user_info)
    
    except ValueError:
        return render_template('exams.html', error="ID Discord invalide (doit être un nombre)")
    except Exception as e:
        print(f"Erreur /exams: {e}")
        import traceback
        traceback.print_exc()
        return render_template('exams.html', error=f"Erreur serveur: {str(e)}")


@app.route('/submit_exam', methods=['POST'])
def submit_exam():
    """Soumet les résultats d'un examen"""
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        exam_id = int(data['exam_id'])
        answers = data['answers']
        
        # Trouver l'examen
        exam = next((e for e in exams_data['exams'] if e['id'] == exam_id), None)
        if not exam:
            return jsonify({'success': False, 'message': 'Examen introuvable'}), 404
        
        # Vérifier la tranche horaire
        now = datetime.now()
        exam_start = datetime.fromisoformat(exam['start_date'])
        exam_end = datetime.fromisoformat(exam['end_date'])
        
        if now < exam_start or now > exam_end:
            return jsonify({
                'success': False, 
                'message': 'Examen non disponible dans cette tranche horaire'
            }), 400
        
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
        passed = percentage >= exam.get('passing_score', 50)
        
        # Sauvegarder le résultat
        exam_result = {
            'user_id': user_id,
            'exam_id': exam_id,
            'exam_title': exam['title'],
            'score': score,
            'total': total_points,
            'percentage': percentage,
            'passed': passed,
            'passing_score': exam.get('passing_score', 50),
            'date': datetime.now().isoformat(),
            'results': results
        }
        
        exam_db.save_exam_result(exam_result)
        
        # Mettre à jour l'utilisateur dans la cohorte
        cohort_manager.update_user_after_exam(user_id, passed)
        
        return jsonify({
            'success': True,
            'score': score,
            'total': total_points,
            'percentage': percentage,
            'passed': passed
        })
        
    except Exception as e:
        print(f"Erreur submit_exam: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/unnotified_exam_results')
def api_unnotified_exam_results():
    """API pour le bot Discord - récupère les résultats non notifiés"""
    results = exam_db.get_unnotified_results(limit=50)
    return jsonify(results)


@app.route('/api/mark_notified', methods=['POST'])
def api_mark_notified():
    """Marque des résultats comme notifiés"""
    try:
        data = request.get_json()
        for result in data.get('results', []):
            exam_db.mark_as_notified(
                result['user_id'],
                result['exam_id'],
                result['date']
            )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
