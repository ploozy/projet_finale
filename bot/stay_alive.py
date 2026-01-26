from flask import Flask, jsonify, request
from threading import Thread
import json
import os

app = Flask('')

# Variable globale pour accéder au bot Discord
discord_bot = None

def set_bot(bot):
    """Définir le bot Discord pour pouvoir l'utiliser dans les endpoints"""
    global discord_bot
    discord_bot = bot

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

@app.route('/api/promote', methods=['POST'])
def promote_user():
    """
    API appelée par Flask après une réussite d'examen
    Effectue immédiatement les changements Discord (rôles, salons)
    """
    global discord_bot

    if not discord_bot:
        return jsonify({'success': False, 'error': 'Bot Discord non initialisé'}), 500

    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        old_groupe = data['old_groupe']
        new_groupe = data['new_groupe']
        passed = data.get('passed', True)
        percentage = data.get('percentage', 0)

        # Déclencher la promotion dans Discord de manière asynchrone
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_promotion():
            from db_connection import SessionLocal
            from models import Utilisateur

            if not discord_bot.guilds:
                return {'success': False, 'error': 'Aucun serveur Discord'}

            guild = discord_bot.guilds[0]
            member = guild.get_member(user_id)

            if not member:
                return {'success': False, 'error': f'Membre {user_id} introuvable sur Discord'}

            print(f"\n{'='*50}")
            print(f"🎉 PROMOTION IMMÉDIATE : {member.name}")
            print(f"   {old_groupe} → {new_groupe}")
            print(f"   Score: {percentage}%")
            print(f"{'='*50}\n")

            # Retirer l'ancien rôle
            old_role = discord.utils.get(guild.roles, name=f"Groupe {old_groupe}")
            if old_role and old_role in member.roles:
                await member.remove_roles(old_role)
                print(f"  ❌ Rôle retiré : {old_role.name}")

            # Créer ou récupérer le nouveau rôle
            new_role = discord.utils.get(guild.roles, name=f"Groupe {new_groupe}")
            if not new_role:
                new_role = await guild.create_role(
                    name=f"Groupe {new_groupe}",
                    color=discord.Color.blue(),
                    mentionable=True
                )
                print(f"  ✅ Rôle créé : {new_role.name}")

            await member.add_roles(new_role)
            print(f"  ✅ Rôle ajouté : {new_role.name}")

            # Créer les salons si nécessaire
            from bot import create_group_channels
            await create_group_channels(guild, new_groupe, new_role)

            # Envoyer les cours du nouveau niveau
            from bot import on_user_level_change
            db = SessionLocal()
            try:
                user_db = db.query(Utilisateur).filter(Utilisateur.user_id == user_id).first()
                if user_db:
                    await on_user_level_change(user_id, user_db.niveau_actuel, new_groupe, guild)
                    print(f"  📚 Ressources envoyées pour niveau {user_db.niveau_actuel}")
            finally:
                db.close()

            # Envoyer un MP de félicitations
            try:
                embed = discord.Embed(
                    title="🎉 Félicitations !",
                    description=f"Tu as **réussi** l'examen !",
                    color=discord.Color.green()
                )
                embed.add_field(name="📊 Score", value=f"{percentage}%", inline=True)
                embed.add_field(name="🎊 Promotion", value=f"**{old_groupe}** → **{new_groupe}**", inline=True)
                embed.add_field(name="🚀 Nouveau niveau", value=f"Tu es maintenant dans le Groupe {new_groupe} !", inline=False)

                await member.send(embed=embed)
                print(f"  ✅ MP de félicitations envoyé")
            except discord.Forbidden:
                print(f"  ⚠️ MP bloqués pour {member.name}")

            print(f"{'='*50}\n")
            return {'success': True}

        result = loop.run_until_complete(do_promotion())
        return jsonify(result)

    except Exception as e:
        print(f"❌ Erreur promotion API: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
