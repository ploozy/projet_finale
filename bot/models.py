"""
Modèles SQLAlchemy pour la base de données
Utilisé par le Bot Discord et le Site Web
"""
from sqlalchemy import Column, Integer, String, BigInteger, Float, Boolean, DateTime, ForeignKey, JSON, CheckConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from db_connection import Base


class Cohorte(Base):
    """Table des cohortes de formation"""
    __tablename__ = 'cohortes'
    
    id = Column(String(20), primary_key=True)  # JAN26-A, FEB26-B
    date_creation = Column(DateTime, nullable=False, default=datetime.now)
    date_premier_examen = Column(DateTime, nullable=False)
    date_fermeture = Column(DateTime, nullable=True)
    niveau_actuel = Column(Integer, nullable=False, default=1)
    statut = Column(String(20), nullable=False, default='en_formation')
    
    # Relations
    utilisateurs = relationship("Utilisateur", back_populates="cohorte", cascade="all, delete-orphan")
    calendrier = relationship("CalendrierExamen", back_populates="cohorte", cascade="all, delete-orphan")
    
    # Contraintes
    __table_args__ = (
        CheckConstraint("statut IN ('en_formation', 'active', 'terminee')", name='chk_statut'),
    )
    
    def __repr__(self):
        return f"<Cohorte {self.id} - {self.statut}>"


class Utilisateur(Base):
    """Table des utilisateurs/étudiants"""
    __tablename__ = 'utilisateurs'
    
    user_id = Column(BigInteger, primary_key=True)  # Discord User ID
    username = Column(String(100), nullable=False)
    cohorte_id = Column(String(20), ForeignKey('cohortes.id', ondelete='SET NULL'), nullable=True)  # Optionnel maintenant
    niveau_actuel = Column(Integer, nullable=False, default=1)
    groupe = Column(String(10), nullable=False, default="1-A")  # Ex: "1-A", "2-B", "Rattrapage Niveau 1"
    examens_reussis = Column(Integer, nullable=False, default=0)
    date_inscription = Column(DateTime, nullable=False, default=datetime.now)
    is_alumni = Column(Boolean, nullable=False, default=False)  # Si l'utilisateur a terminé le niveau 5
    in_rattrapage = Column(Boolean, nullable=False, default=False)  # Si l'utilisateur est en rattrapage
    
    # Colonnes pour le système de vote
    has_voted = Column(Boolean, nullable=False, default=False)
    current_exam_period = Column(String(50), nullable=True)
    bonus_points = Column(Float, nullable=False, default=0.0)
    bonus_level = Column(String(20), nullable=True)  # 'or', 'argent', 'bronze'
    
    # Relations
    cohorte = relationship("Cohorte", back_populates="utilisateurs")
    reviews = relationship("Review", back_populates="utilisateur", cascade="all, delete-orphan")
    exam_results = relationship("ExamResult", back_populates="utilisateur", cascade="all, delete-orphan")
    historique = relationship("HistoriqueCohorte", back_populates="utilisateur", cascade="all, delete-orphan")
    
    # Contraintes
    __table_args__ = (
        CheckConstraint("niveau_actuel BETWEEN 1 AND 5", name='chk_niveau'),
    )
    
    def __repr__(self):
        return f"<Utilisateur {self.username} - Cohorte {self.cohorte_id}>"


class CalendrierExamen(Base):
    """Table du calendrier des examens par cohorte"""
    __tablename__ = 'calendrier_examens'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cohorte_id = Column(String(20), ForeignKey('cohortes.id', ondelete='CASCADE'), nullable=False)
    niveau = Column(Integer, nullable=False)
    exam_id = Column(Integer, nullable=False)  # Référence vers exam.json
    date_examen = Column(DateTime, nullable=False)
    
    # Relations
    cohorte = relationship("Cohorte", back_populates="calendrier")
    
    # Contraintes
    __table_args__ = (
        CheckConstraint("niveau BETWEEN 1 AND 5", name='chk_niveau_cal'),
    )
    
    def __repr__(self):
        return f"<CalendrierExamen {self.cohorte_id} - Niveau {self.niveau}>"


class HistoriqueCohorte(Base):
    """Historique des cohortes auxquelles un utilisateur a appartenu"""
    __tablename__ = 'historique_cohortes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    cohorte_id = Column(String(20), nullable=False)
    date_ajout = Column(DateTime, nullable=False, default=datetime.now)
    
    # Relations
    utilisateur = relationship("Utilisateur", back_populates="historique")
    
    def __repr__(self):
        return f"<HistoriqueCohorte {self.user_id} - {self.cohorte_id}>"


class Review(Base):
    """Table des révisions espacées (Spaced Repetition)"""
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    question_id = Column(Integer, nullable=False)
    next_review = Column(DateTime, nullable=False)
    interval_days = Column(Float, nullable=False)
    repetitions = Column(Integer, nullable=False, default=0)
    easiness_factor = Column(Float, nullable=False, default=2.5)
    
    # Relations
    utilisateur = relationship("Utilisateur", back_populates="reviews")
    
    # Index pour optimiser les requêtes
    __table_args__ = (
        CheckConstraint("user_id >= 0", name='chk_user_id_review'),
    )
    
    def __repr__(self):
        return f"<Review {self.user_id} - Q{self.question_id}>"


class ExamResult(Base):
    """Table des résultats d'examens"""
    __tablename__ = 'exam_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    exam_id = Column(Integer, nullable=False)
    exam_title = Column(String(200), nullable=False)
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=False)
    passing_score = Column(Integer, nullable=False)
    date = Column(DateTime, nullable=False, default=datetime.now)
    notified = Column(Boolean, nullable=False, default=False)
    results = Column(JSON, nullable=True)  # Détails des réponses
    
    # Relations
    utilisateur = relationship("Utilisateur", back_populates="exam_results")
    
    def __repr__(self):
        return f"<ExamResult {self.user_id} - {self.exam_title} ({self.percentage}%)>"


class CourseQuizResult(Base):
    """Table des résultats de quiz sur les cours"""
    __tablename__ = 'course_quiz_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    course_id = Column(Integer, nullable=False)  # ID du cours (1, 2, 3, 4)
    quiz_question_id = Column(String(50), nullable=False)  # Ex: "poo_q1", "struct_q2"
    quality = Column(Integer, nullable=False)  # 0-5 (SM-2)
    date = Column(DateTime, nullable=False, default=datetime.now)
    
    def __repr__(self):
        return f"<CourseQuizResult {self.user_id} - Cours {self.course_id} Q{self.quiz_question_id}>"


class Vote(Base):
    """Table des votes pour le système de récompense d'entraide"""
    __tablename__ = 'votes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    voter_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    voted_for_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    exam_period_id = Column(String(50), ForeignKey('exam_periods.id', ondelete='CASCADE'), nullable=False)
    date = Column(DateTime, nullable=False, default=datetime.now)
    
    def __repr__(self):
        return f"<Vote {self.voter_id} -> {self.voted_for_id}>"


class ExamPeriod(Base):
    """Table des périodes d'examen (6h fixes par groupe)"""
    __tablename__ = 'exam_periods'

    id = Column(String(50), primary_key=True)  # Ex: "2026-01-15_group1"
    group_number = Column(Integer, nullable=False)
    groupe = Column(String(10), nullable=True)  # Ex: "1-A", "Rattrapage Niveau 1"
    vote_start_time = Column(DateTime, nullable=False)  # Votes ouverts 24h avant
    start_time = Column(DateTime, nullable=False)  # Début de l'examen
    end_time = Column(DateTime, nullable=False)  # Fin de l'examen (6h après start_time)
    votes_closed = Column(Boolean, nullable=False, default=False)
    bonuses_applied = Column(Boolean, nullable=False, default=False)
    is_rattrapage = Column(Boolean, nullable=False, default=False)  # Si c'est un examen de rattrapage

    def __repr__(self):
        return f"<ExamPeriod {self.id} - Group {self.group_number}>"


class WaitingList(Base):
    """Table des listes d'attente pour les groupes"""
    __tablename__ = 'waiting_lists'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    niveau = Column(Integer, nullable=False)  # Niveau attendu
    target_group = Column(String(10), nullable=True)  # Groupe cible (ex: "1-D") ou None si général
    date_ajout = Column(DateTime, nullable=False, default=datetime.now)
    type_waiting = Column(String(20), nullable=False, default='nouveau_groupe')  # 'nouveau_groupe' ou 'groupe_plein'
    raison = Column(String(100), nullable=True)  # Raison de l'attente

    def __repr__(self):
        return f"<WaitingList {self.user_id} - Niveau {self.niveau} - {self.target_group or 'général'}>"


class RattrapageExam(Base):
    """Table des examens de rattrapage programmés pour chaque utilisateur"""
    __tablename__ = 'rattrapage_exams'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('utilisateurs.user_id', ondelete='CASCADE'), nullable=False)
    niveau = Column(Integer, nullable=False)  # Niveau à rattraper
    failed_percentage = Column(Float, nullable=False)  # Note obtenue lors de l'échec
    delai_jours = Column(Float, nullable=False)  # Délai en jours avant l'examen
    date_echec = Column(DateTime, nullable=False, default=datetime.now)  # Date de l'échec
    date_exam_rattrapage = Column(DateTime, nullable=False)  # Date calculée de l'examen
    completed = Column(Boolean, nullable=False, default=False)  # Si l'examen a été passé
    groupe_rattrapage = Column(String(30), nullable=False)  # Ex: "Rattrapage Niveau 1"

    def __repr__(self):
        return f"<RattrapageExam {self.user_id} - Niveau {self.niveau} - {self.date_exam_rattrapage}>"
