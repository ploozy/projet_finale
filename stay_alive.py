from flask import Flask, jsonify
from threading import Thread
import json
import os

app = Flask('')

@app.route('/')
def home():
    return "Le bot est en ligne"

@app.route('/api/user/<user_id>')
def get_user_cohort(user_id):
    """API pour récupérer la cohorte d'un utilisateur"""
    try:
        cohortes_file = os.path.join(os.path.dirname(__file__), 'cohortes.json')
        
        if not os.path.exists(cohortes_file):
            return jsonify({
                'success': False, 
                'error': 'Fichier cohortes.json introuvable'
            }), 500
        
        with open(cohortes_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        utilisateurs = data.get('utilisateurs', [])
        
        for user in utilisateurs:
            if str(user.get('user_id')) == str(user_id):
                return jsonify({
                    'success': True,
                    'data': {
                        'user_id': user.get('user_id'),
                        'username': user.get('username'),
                        'cohorte_id': user.get('cohorte_id'),
                        'niveau_actuel': user.get('niveau_actuel', 1),
                        'examens_reussis': user.get('examens_reussis', 0)
                    }
                })
        
        return jsonify({
            'success': False, 
            'error': f'Utilisateur {user_id} non trouvé'
        }), 404
    
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
