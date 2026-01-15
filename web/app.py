from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
from datetime import datetime
import os
import requests

# ✅ UTILISATION DE POSTGRESQL
from cohorte_manager_sql import CohortManagerSQL
from exam_result_database_sql import ExamResultDatabaseSQL

app = Flask(__name__)
app.secret_key = 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2'

# URL du bot Discord (pour les notifications)
BOT_URL = os.getenv('BOT_URL', 'http://localhost:8080')

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
    """Page d'accueil"""
    return render_template('index.html')


@app.route('/course/<int:course_id>')
def course_detail(course_id):
    """Affichage d'un cours"""
    course = next((c for c in courses_content['courses'] if c['id'] == course_id), None)

    if not course:
        return "Cours non trouvé", 404

    return render_template('course_detail.html', course=course)


@app.route('/exams')
def exams_list():
    """Liste des examens disponibles"""
    return render_template('exams.html', exams=exams_data['exams'])


@app.route('/exam/<int:exam_id>')
def exam_take(exam_id):
    """Passer un examen"""
    exam = next((e for e in exams_data['exams'] if e['id'] == exam_id), None)

    if not exam:
        return "Examen non trouvé", 404

    return render_template('exam_take.html', exam=exam)


@app.route('/api/check_user_level', methods=['POST'])
def check_user_level():
    """
    Vérifie le niveau d'un utilisateur et la disponibilité de l'examen
    """
    try:
        data = request.json
        user_id = int(data['user_id'])
        exam_id = int(data['exam_id'])

        # Récupérer les informations de l'utilisateur
        user_info = cohort_manager.get_user_info(user_id)

        if not user_info:
            return jsonify({
                'success': False,
                'message': 'Utilisateur non inscrit'
            }), 403

        # Vérifier que l'examen correspond au niveau de l'utilisateur
        exam = next((e for e in exams_data['exams'] if e['id'] == exam_id), None)

        if not exam:
            return jsonify({
                'success': False,
                'message': 'Examen non trouvé'
            }), 404

        if exam['group'] != user_info['niveau_actuel']:
            return jsonify({
                'success': False,
                'message': f"Cet examen est pour le niveau {exam['group']}. Vous êtes niveau {user_info['niveau_actuel']}"
            }), 403

        # Vérifier les dates d'examen
        next_exam = cohort_manager.get_next_exam_for_user(user_id)

        if not next_exam:
            return jsonify({
                'success': False,
                'message': 'Aucun examen planifié'
            }), 403

        date_debut = datetime.fromisoformat(next_exam['date_debut'])
        date_fin = datetime.fromisoformat(next_exam['date_fin'])
        now = datetime.now()

        if now < date_debut:
            return jsonify({
                'success': False,
                'message': f"L'examen commence le {date_debut.strftime('%d/%m/%Y à %H:%M')}"
            }), 403

        if now > date_fin:
            return jsonify({
                'success': False,
                'message': f"L'examen s'est terminé le {date_fin.strftime('%d/%m/%Y à %H:%M')}"
            }), 403

        # Tout est OK
        return jsonify({
            'success': True,
            'user_info': user_info,
            'exam_window': {
                'debut': date_debut.isoformat(),
                'fin': date_fin.isoformat()
            }
        })

    except Exception as e:
        print(f"❌ Erreur check_user_level: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/submit_exam', methods=['POST'])
def submit_exam():
    """Soumet un examen complété"""
    try:
        data = request.json
        user_id = int(data['user_id'])
        exam_id = int(data['exam_id'])
        answers = data['answers']

        # Récupérer l'examen
        exam = next((e for e in exams_data['exams'] if e['id'] == exam_id), None)

        if not exam:
            return jsonify({
                'success': False,
                'message': 'Examen non trouvé'
            }), 404

        # Calculer le score
        score = 0
        total_points = 0
        results = []

        for question in exam['questions']:
            total_points += question['points']
            user_answer = answers.get(str(question['id']))
            is_correct = (user_answer == question['correct'])

            if is_correct:
                score += question['points']

            results.append({
                'question_id': question['id'],
                'user_answer': user_answer,
                'correct_answer': question['correct'],
                'is_correct': is_correct,
                'points': question['points'] if is_correct else 0
            })

        # Calculer le pourcentage
        percentage = (score / total_points) * 100
        passed = percentage >= exam['passing_score']

        # Enregistrer le résultat
        exam_result = {
            'user_id': user_id,
            'exam_id': exam_id,
            'exam_title': exam['title'],
            'score': score,
            'total': total_points,
            'percentage': round(percentage, 2),
            'passed': passed,
            'passing_score': exam['passing_score'],
            'date': datetime.now(),
            'results': results
        }

        exam_db.save_exam_result(exam_result)

        # Mettre à jour le niveau de l'utilisateur
        message, nouveau_niveau, nouveau_sous_groupe = cohort_manager.update_user_after_exam(
            user_id, passed
        )

        # Notifier le bot Discord pour la mise à jour des rôles
        try:
            response = requests.post(
                f"{BOT_URL}/api/submit_exam",
                json={
                    'user_id': user_id,
                    'exam_id': exam_id,
                    'passed': passed,
                    **exam_result
                },
                timeout=5
            )
        except Exception as e:
            print(f"⚠️ Impossible de notifier le bot: {e}")

        return jsonify({
            'success': True,
            'passed': passed,
            'score': score,
            'total': total_points,
            'percentage': percentage,
            'message': message,
            'nouveau_niveau': nouveau_niveau,
            'nouveau_sous_groupe': nouveau_sous_groupe,
            'results': results
        })

    except Exception as e:
        print(f"❌ Erreur submit_exam: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/get_user_info/<int:user_id>')
def get_user_info(user_id):
    """Récupère les informations d'un utilisateur"""
    try:
        user_info = cohort_manager.get_user_info(user_id)

        if not user_info:
            return jsonify({
                'success': False,
                'message': 'Utilisateur non trouvé'
            }), 404

        return jsonify({
            'success': True,
            'user': user_info
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/get_exam_results/<int:user_id>')
def get_exam_results(user_id):
    """Récupère les résultats d'examens d'un utilisateur"""
    try:
        results = exam_db.get_user_exam_results(user_id)

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
