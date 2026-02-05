"""
Gestionnaire de Groupes - Remplace le système de cohortes

Ce système gère :
- L'inscription dans les groupes avec vérification du temps de formation
- Les waiting lists (deux types)
- Les rattrapages avec délais selon la note
- Les alumni (niveau 5 terminé)
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from sqlalchemy.orm import Session
from models import Utilisateur, ExamPeriod, WaitingList, RattrapageExam
from cohort_config import (
    TEMPS_FORMATION_MINIMUM,
    MAX_MEMBRES_PAR_GROUPE,
    MIN_PERSONNES_NOUVEAU_GROUPE,
    LETTRES_GROUPES,
    DUREE_EXAMEN_NORMALE,
    DUREE_EXAMEN_RATTRAPAGE,
    get_delai_rattrapage,
    get_categorie_note
)


class GroupManager:
    """Gestionnaire de groupes (remplace CohorteManagerSQL)"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== INSCRIPTION ====================

    def register_user(self, user_id: int, username: str, niveau: int = 1) -> Tuple[str, dict]:
        """
        Inscrit un nouvel utilisateur dans un groupe

        Returns:
            Tuple(groupe, info_dict) où info_dict contient :
            - 'status': 'direct', 'needs_confirmation', ou 'waiting_list'
            - 'temps_restant_jours': si needs_confirmation
            - 'temps_formation_minimum': si needs_confirmation
            - 'waiting_list_type': si waiting_list
            - 'target_group': si waiting_list pour nouveau groupe
        """
        # Vérifier si l'utilisateur existe déjà
        existing_user = self.db.query(Utilisateur).filter(
            Utilisateur.user_id == user_id
        ).first()

        if existing_user:
            return existing_user.groupe, {'status': 'already_registered'}

        # Chercher un groupe disponible
        groupe_info = self._find_available_group(niveau)

        if groupe_info['status'] == 'direct':
            # Inscription directe
            user = Utilisateur(
                user_id=user_id,
                username=username,
                niveau_actuel=niveau,
                groupe=groupe_info['groupe'],
                examens_reussis=0,
                cohorte_id=None  # Plus de cohortes
            )
            self.db.add(user)
            self.db.commit()

            return groupe_info['groupe'], {'status': 'direct'}

        elif groupe_info['status'] == 'needs_confirmation':
            # Temps insuffisant, demander confirmation
            return None, groupe_info

        elif groupe_info['status'] == 'waiting_list':
            # Ajouter à la waiting list
            waiting = WaitingList(
                user_id=user_id,
                niveau=niveau,
                target_group=groupe_info.get('target_group'),
                type_waiting=groupe_info['waiting_list_type'],
                raison=groupe_info.get('raison', '')
            )
            self.db.add(waiting)
            self.db.commit()

            return None, groupe_info

    def confirm_registration_with_insufficient_time(
        self,
        user_id: int,
        username: str,
        niveau: int,
        groupe: str
    ) -> str:
        """
        Confirme l'inscription d'un utilisateur malgré un temps insuffisant

        Args:
            user_id: ID Discord de l'utilisateur
            username: Nom d'utilisateur
            niveau: Niveau du groupe
            groupe: Groupe à rejoindre

        Returns:
            Le groupe assigné
        """
        user = Utilisateur(
            user_id=user_id,
            username=username,
            niveau_actuel=niveau,
            groupe=groupe,
            examens_reussis=0,
            cohorte_id=None
        )
        self.db.add(user)
        self.db.commit()

        return groupe

    def _find_available_group(self, niveau: int) -> dict:
        """
        Trouve un groupe disponible pour un niveau donné

        Returns:
            dict avec :
            - 'status': 'direct', 'needs_confirmation', ou 'waiting_list'
            - 'groupe': nom du groupe (si direct ou needs_confirmation)
            - 'temps_restant_jours': jours avant examen (si needs_confirmation)
            - 'temps_formation_minimum': temps minimum requis (si needs_confirmation)
            - 'waiting_list_type': type de waiting list (si waiting_list)
            - 'target_group': groupe cible (si waiting_list pour nouveau groupe)
        """
        temps_minimum = TEMPS_FORMATION_MINIMUM.get(niveau, 3)

        # Parcourir toutes les lettres possibles
        for lettre in LETTRES_GROUPES:
            groupe = f"{niveau}-{lettre}"

            # Compter les membres du groupe
            count = self.db.query(Utilisateur).filter(
                Utilisateur.groupe == groupe,
                Utilisateur.in_rattrapage == False
            ).count()

            if count >= MAX_MEMBRES_PAR_GROUPE:
                continue  # Groupe plein

            # Groupe a de la place, vérifier le temps restant avant examen
            exam_period = self._get_next_exam_for_group(groupe, niveau)

            if not exam_period:
                # Pas d'examen programmé, inscription directe
                return {
                    'status': 'direct',
                    'groupe': groupe
                }

            # Calculer le temps restant
            now = datetime.utcnow()
            temps_restant = (exam_period.start_time - now).total_seconds() / 86400  # en jours

            if temps_restant >= temps_minimum:
                # Temps suffisant, inscription directe
                return {
                    'status': 'direct',
                    'groupe': groupe
                }
            else:
                # Temps insuffisant, demander confirmation
                return {
                    'status': 'needs_confirmation',
                    'groupe': groupe,
                    'temps_restant_jours': temps_restant,
                    'temps_formation_minimum': temps_minimum
                }

        # Tous les groupes A-Z sont pleins → Waiting List générale
        return {
            'status': 'waiting_list',
            'waiting_list_type': 'groupe_plein',
            'raison': f'Tous les groupes du niveau {niveau} sont pleins (A-Z)'
        }

    def _get_next_exam_for_group(self, groupe: str, niveau: int) -> Optional[ExamPeriod]:
        """
        Récupère le prochain examen programmé pour un groupe.
        Cherche d'abord les périodes spécifiques au groupe,
        puis les périodes legacy (sans groupe spécifique).
        """
        now = datetime.utcnow()

        # 1. Chercher une période spécifique à ce groupe
        period = self.db.query(ExamPeriod).filter(
            ExamPeriod.group_number == niveau,
            ExamPeriod.groupe == groupe,
            ExamPeriod.start_time > now
        ).order_by(ExamPeriod.start_time).first()

        if period:
            return period

        # 2. Fallback : période legacy sans groupe spécifique
        return self.db.query(ExamPeriod).filter(
            ExamPeriod.group_number == niveau,
            ExamPeriod.groupe == None,
            ExamPeriod.start_time > now
        ).order_by(ExamPeriod.start_time).first()

    # ==================== WAITING LIST ====================

    def check_and_process_waiting_lists(self, niveau: int):
        """
        Vérifie et traite les waiting lists pour un niveau donné

        - Si 7 personnes ou plus : créer un nouveau groupe
        - Sinon : assigner aux groupes qui se libèrent
        """
        # Type 1 : Waiting list pour nouveau groupe
        waiting_nouveau = self.db.query(WaitingList).filter(
            WaitingList.niveau == niveau,
            WaitingList.type_waiting == 'nouveau_groupe'
        ).order_by(WaitingList.date_ajout).all()

        if len(waiting_nouveau) >= MIN_PERSONNES_NOUVEAU_GROUPE:
            # Créer un nouveau groupe
            nouveau_groupe = self._create_next_group(niveau)

            # Assigner les 7 premières personnes
            for i, waiting in enumerate(waiting_nouveau[:MIN_PERSONNES_NOUVEAU_GROUPE]):
                user = self.db.query(Utilisateur).filter(
                    Utilisateur.user_id == waiting.user_id
                ).first()

                if not user:
                    # Créer l'utilisateur (était en waiting list avant inscription)
                    user = Utilisateur(
                        user_id=waiting.user_id,
                        username=f"User{waiting.user_id}",  # À récupérer depuis Discord
                        niveau_actuel=niveau,
                        groupe=nouveau_groupe,
                        examens_reussis=0,
                        cohorte_id=None
                    )
                    self.db.add(user)
                else:
                    user.groupe = nouveau_groupe

                # Supprimer de la waiting list
                self.db.delete(waiting)

            self.db.commit()

            print(f"✅ Nouveau groupe {nouveau_groupe} créé avec {MIN_PERSONNES_NOUVEAU_GROUPE} membres")

        # Type 2 : Waiting list générale (groupes pleins)
        waiting_general = self.db.query(WaitingList).filter(
            WaitingList.niveau == niveau,
            WaitingList.type_waiting == 'groupe_plein'
        ).order_by(WaitingList.date_ajout).all()

        # Assigner aux groupes qui ont de la place
        for waiting in waiting_general:
            groupe_info = self._find_available_group(niveau)

            if groupe_info['status'] == 'direct':
                user = self.db.query(Utilisateur).filter(
                    Utilisateur.user_id == waiting.user_id
                ).first()

                if not user:
                    user = Utilisateur(
                        user_id=waiting.user_id,
                        username=f"User{waiting.user_id}",
                        niveau_actuel=niveau,
                        groupe=groupe_info['groupe'],
                        examens_reussis=0,
                        cohorte_id=None
                    )
                    self.db.add(user)
                else:
                    user.groupe = groupe_info['groupe']

                self.db.delete(waiting)
                self.db.commit()

                print(f"✅ Utilisateur {waiting.user_id} assigné depuis la waiting list au groupe {groupe_info['groupe']}")

    def _create_next_group(self, niveau: int) -> str:
        """Crée le prochain groupe disponible pour un niveau"""
        for lettre in LETTRES_GROUPES:
            groupe = f"{niveau}-{lettre}"

            # Vérifier si le groupe existe déjà
            exists = self.db.query(Utilisateur).filter(
                Utilisateur.groupe == groupe
            ).first()

            if not exists:
                return groupe

        # Tous les groupes A-Z existent, créer Z+1 (ne devrait pas arriver)
        return f"{niveau}-Z1"

    # ==================== PROMOTION ====================

    def promote_user(self, user_id: int) -> Tuple[str, str]:
        """
        Promeut un utilisateur au niveau suivant

        Returns:
            Tuple(old_groupe, new_groupe)
        """
        user = self.db.query(Utilisateur).filter(
            Utilisateur.user_id == user_id
        ).first()

        if not user:
            raise ValueError(f"Utilisateur {user_id} introuvable")

        old_groupe = user.groupe
        old_niveau = user.niveau_actuel
        new_niveau = old_niveau + 1

        if new_niveau > 5:
            # Niveau 5 terminé → Alumni
            user.is_alumni = True
            user.niveau_actuel = 5
            user.examens_reussis = 5
            self.db.commit()

            return old_groupe, "Alumni"

        # Trouver un groupe disponible au nouveau niveau
        groupe_info = self._find_available_group(new_niveau)

        if groupe_info['status'] == 'direct':
            user.niveau_actuel = new_niveau
            user.groupe = groupe_info['groupe']
            user.examens_reussis += 1
            user.in_rattrapage = False  # Sortir du rattrapage si nécessaire
            self.db.commit()

            return old_groupe, groupe_info['groupe']

        elif groupe_info['status'] == 'waiting_list':
            # Ajouter à la waiting list
            waiting = WaitingList(
                user_id=user_id,
                niveau=new_niveau,
                target_group=groupe_info.get('target_group'),
                type_waiting=groupe_info['waiting_list_type'],
                raison=f"Promotion depuis {old_groupe}"
            )
            self.db.add(waiting)
            self.db.commit()

            return old_groupe, f"Waiting List (Niveau {new_niveau})"

        else:
            # Ne devrait pas arriver
            return old_groupe, old_groupe

    # ==================== RATTRAPAGE ====================

    def handle_exam_failure(self, user_id: int, niveau: int, percentage: float) -> dict:
        """
        Gère l'échec d'un examen avec système de rattrapage

        Args:
            user_id: ID de l'utilisateur
            niveau: Niveau de l'examen raté
            percentage: Note obtenue (0-100)

        Returns:
            dict avec :
            - 'action': 'rattrapage', 'assign_group', ou 'waiting_list'
            - 'groupe': groupe assigné (si applicable)
            - 'delai_jours': délai avant l'examen (si rattrapage)
            - 'date_exam': date de l'examen de rattrapage
            - 'categorie': catégorie de note
        """
        user = self.db.query(Utilisateur).filter(
            Utilisateur.user_id == user_id
        ).first()

        if not user:
            raise ValueError(f"Utilisateur {user_id} introuvable")

        categorie = get_categorie_note(percentage)
        delai_jours = get_delai_rattrapage(percentage, niveau)

        # CAS 1 : Note < 20% → Chercher un groupe avec temps suffisant ou waiting list
        if percentage < 20:
            # Chercher un groupe avec temps_restant_examen ≥ temps_formation_minimum
            temps_minimum = TEMPS_FORMATION_MINIMUM.get(niveau, 3)
            groupe_trouve = None

            for lettre in LETTRES_GROUPES:
                groupe = f"{niveau}-{lettre}"

                # Vérifier si le groupe a de la place
                count = self.db.query(Utilisateur).filter(
                    Utilisateur.groupe == groupe,
                    Utilisateur.in_rattrapage == False
                ).count()

                if count >= MAX_MEMBRES_PAR_GROUPE:
                    continue

                # Vérifier le temps restant avant examen
                exam_period = self._get_next_exam_for_group(groupe, niveau)

                if not exam_period:
                    continue

                now = datetime.utcnow()
                temps_restant_jours = (exam_period.start_time - now).total_seconds() / 86400

                if temps_restant_jours >= temps_minimum:
                    groupe_trouve = groupe
                    break

            if groupe_trouve:
                # Assigner au groupe trouvé
                user.groupe = groupe_trouve
                user.in_rattrapage = False
                self.db.commit()

                return {
                    'action': 'assign_group',
                    'groupe': groupe_trouve,
                    'categorie': categorie
                }
            else:
                # Aucun groupe disponible → Waiting list
                waiting = WaitingList(
                    user_id=user_id,
                    niveau=niveau,
                    target_group=None,
                    type_waiting='groupe_plein',
                    raison=f"Échec avec {percentage}%, besoin d'aide"
                )
                self.db.add(waiting)
                self.db.commit()

                return {
                    'action': 'waiting_list',
                    'categorie': categorie,
                    'raison': 'Aucun groupe disponible avec temps suffisant'
                }

        # CAS 2 : Note ≥ 20% → Groupe rattrapage avec délai
        else:
            groupe_rattrapage = f"Rattrapage Niveau {niveau}"

            # Calculer la date de l'examen de rattrapage
            now = datetime.utcnow()
            date_exam_rattrapage = now + timedelta(days=delai_jours)

            # Créer l'entrée de rattrapage
            rattrapage = RattrapageExam(
                user_id=user_id,
                niveau=niveau,
                failed_percentage=percentage,
                delai_jours=delai_jours,
                date_echec=now,
                date_exam_rattrapage=date_exam_rattrapage,
                completed=False,
                groupe_rattrapage=groupe_rattrapage
            )
            self.db.add(rattrapage)

            # Mettre à jour l'utilisateur
            user.groupe = groupe_rattrapage
            user.in_rattrapage = True
            self.db.commit()

            return {
                'action': 'rattrapage',
                'groupe': groupe_rattrapage,
                'delai_jours': delai_jours,
                'date_exam': date_exam_rattrapage,
                'categorie': categorie
            }

    def get_rattrapage_exam_info(self, user_id: int) -> Optional[dict]:
        """
        Récupère les informations de l'examen de rattrapage pour un utilisateur

        Returns:
            dict avec date_exam, delai_jours, temps_restant, etc. ou None
        """
        rattrapage = self.db.query(RattrapageExam).filter(
            RattrapageExam.user_id == user_id,
            RattrapageExam.completed == False
        ).order_by(RattrapageExam.date_exam_rattrapage.desc()).first()

        if not rattrapage:
            return None

        now = datetime.utcnow()
        temps_restant = (rattrapage.date_exam_rattrapage - now).total_seconds()

        return {
            'niveau': rattrapage.niveau,
            'date_exam': rattrapage.date_exam_rattrapage,
            'delai_jours': rattrapage.delai_jours,
            'temps_restant_secondes': max(0, temps_restant),
            'temps_restant_jours': max(0, temps_restant / 86400),
            'peut_passer': temps_restant <= 0,
            'failed_percentage': rattrapage.failed_percentage,
            'groupe_rattrapage': rattrapage.groupe_rattrapage
        }

    def mark_rattrapage_completed(self, user_id: int):
        """Marque l'examen de rattrapage comme complété"""
        rattrapage = self.db.query(RattrapageExam).filter(
            RattrapageExam.user_id == user_id,
            RattrapageExam.completed == False
        ).order_by(RattrapageExam.date_exam_rattrapage.desc()).first()

        if rattrapage:
            rattrapage.completed = True
            self.db.commit()

    # ==================== PÉRIODES D'EXAMEN ====================

    def create_exam_period(
        self,
        groupe: str,
        niveau: int,
        start_time: datetime,
        is_rattrapage: bool = False
    ) -> ExamPeriod:
        """
        Crée une période d'examen pour un groupe

        Args:
            groupe: Nom du groupe (ex: "1-A" ou "Rattrapage Niveau 1")
            niveau: Niveau de l'examen
            start_time: Date de début de l'examen (déjà en UTC)
            is_rattrapage: Si c'est un examen de rattrapage

        Returns:
            L'ExamPeriod créé
        """
        # Calculer la fin (6h après le début)
        duree = DUREE_EXAMEN_RATTRAPAGE if is_rattrapage else DUREE_EXAMEN_NORMALE
        end_time = start_time + timedelta(hours=duree)

        # Calculer l'ouverture des votes (24h avant)
        vote_start_time = start_time - timedelta(days=1)

        # Générer l'ID
        period_id = f"{start_time.strftime('%Y-%m-%d_%H%M')}_{groupe.replace(' ', '_')}"

        # Créer la période
        exam_period = ExamPeriod(
            id=period_id,
            group_number=niveau,
            groupe=groupe,
            vote_start_time=vote_start_time,
            start_time=start_time,
            end_time=end_time,
            votes_closed=False,
            bonuses_applied=False,
            is_rattrapage=is_rattrapage
        )

        self.db.add(exam_period)
        self.db.commit()

        return exam_period

    def get_active_exam_period(self, user_id: int) -> Optional[ExamPeriod]:
        """
        Récupère la période d'examen active pour un utilisateur

        Returns:
            ExamPeriod actif ou None
        """
        user = self.db.query(Utilisateur).filter(
            Utilisateur.user_id == user_id
        ).first()

        if not user:
            return None

        now = datetime.utcnow()

        return self.db.query(ExamPeriod).filter(
            ExamPeriod.group_number == user.niveau_actuel,
            ExamPeriod.groupe == user.groupe,
            ExamPeriod.start_time <= now,
            ExamPeriod.end_time >= now
        ).first()

    # ==================== UTILITAIRES ====================

    def get_group_members(self, groupe: str) -> List[Utilisateur]:
        """Récupère tous les membres d'un groupe"""
        return self.db.query(Utilisateur).filter(
            Utilisateur.groupe == groupe,
            Utilisateur.in_rattrapage == False
        ).all()

    def get_group_member_count(self, groupe: str) -> int:
        """Compte les membres d'un groupe"""
        return self.db.query(Utilisateur).filter(
            Utilisateur.groupe == groupe,
            Utilisateur.in_rattrapage == False
        ).count()

    def get_waiting_list_count(self, niveau: int) -> int:
        """Compte les personnes en waiting list pour un niveau"""
        return self.db.query(WaitingList).filter(
            WaitingList.niveau == niveau
        ).count()

    def get_rattrapage_members(self, niveau: int) -> List[Utilisateur]:
        """Récupère tous les membres du groupe de rattrapage d'un niveau"""
        groupe_rattrapage = f"Rattrapage Niveau {niveau}"

        return self.db.query(Utilisateur).filter(
            Utilisateur.groupe == groupe_rattrapage,
            Utilisateur.in_rattrapage == True
        ).all()

