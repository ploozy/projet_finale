#!/bin/bash

# 🚀 Script d'Initialisation GitHub
# Automatise la mise en ligne du projet

echo "🚀 Initialisation du dépôt GitHub"
echo "=================================="
echo ""

# Vérifier si Git est installé
if ! command -v git &> /dev/null; then
    echo "❌ Git n'est pas installé. Installez-le depuis https://git-scm.com/"
    exit 1
fi

echo "✅ Git détecté"
echo ""

# Demander les informations
read -p "📝 Entrez votre nom d'utilisateur GitHub : " GITHUB_USERNAME
read -p "📝 Entrez le nom du dépôt (ex: plateforme-formation-python) : " REPO_NAME

echo ""
echo "🔍 Configuration :"
echo "   Utilisateur : $GITHUB_USERNAME"
echo "   Dépôt : $REPO_NAME"
echo "   URL : https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo ""

read -p "✅ Confirmer ? (y/n) : " CONFIRM

if [ "$CONFIRM" != "y" ]; then
    echo "❌ Annulé"
    exit 0
fi

echo ""
echo "🔧 Initialisation Git..."

# Initialiser Git si nécessaire
if [ ! -d ".git" ]; then
    git init
    echo "✅ Git initialisé"
else
    echo "ℹ️ Git déjà initialisé"
fi

# Configurer Git (si première fois)
echo ""
read -p "📧 Entrez votre email GitHub : " GIT_EMAIL
read -p "👤 Entrez votre nom : " GIT_NAME

git config user.email "$GIT_EMAIL"
git config user.name "$GIT_NAME"

echo "✅ Configuration Git enregistrée"
echo ""

# Ajouter tous les fichiers
echo "📦 Ajout des fichiers..."
git add .

# Créer le premier commit
echo "💾 Création du commit..."
git commit -m "Initial commit - Plateforme de formation complète

✨ Features:
- Bot Discord avec système de QCM
- Site web avec examens par groupe
- Base de données PostgreSQL
- Révisions espacées (SM-2)
- Documentation complète

🗂️ Structure:
- bot/ : Bot Discord
- web/ : Site Flask
- Documentation : 7 fichiers MD"

echo "✅ Commit créé"
echo ""

# Ajouter le remote
echo "🔗 Ajout du remote GitHub..."
git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"

echo "✅ Remote ajouté"
echo ""

# Créer la branche main
git branch -M main

echo "🚀 Push vers GitHub..."
echo ""
echo "⚠️  Vous allez être redirigé vers GitHub pour l'authentification"
echo ""

# Push vers GitHub
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Succès ! Votre projet est maintenant sur GitHub !"
    echo ""
    echo "🔗 URL de votre dépôt :"
    echo "   https://github.com/$GITHUB_USERNAME/$REPO_NAME"
    echo ""
    echo "📋 Prochaines étapes :"
    echo "   1. Ajoutez une photo de profil au dépôt (Settings → Social preview)"
    echo "   2. Ajoutez des topics (Discord, Python, Flask, PostgreSQL)"
    echo "   3. Liez le dépôt à Render pour auto-deploy"
    echo ""
else
    echo ""
    echo "❌ Erreur lors du push"
    echo ""
    echo "💡 Solutions possibles :"
    echo "   1. Vérifiez que le dépôt existe sur GitHub"
    echo "   2. Vérifiez votre authentification GitHub"
    echo "   3. Utilisez 'gh auth login' si vous avez GitHub CLI"
    echo ""
    echo "📖 Ou suivez GITHUB.md pour les alternatives"
fi
