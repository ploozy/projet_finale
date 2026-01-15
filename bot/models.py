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

    __table_args__ = (
        CheckConstraint("statut IN ('en_formation', 'active', 'terminee')", name='chk_statut'),
    )

    def __repr__(self):
        return f"<Cohorte {self.id} (Niveau {self.niveau_actuel})>"


class Utilisateur(Base):
    """Table des utilisateurs/étudiants"""
    __tablename__ = 'utilisateurs'

    user_id = Column(BigInteger, primary_key=True)  # Discord User ID
    username = Column(String(100), nullable=False)
    cohorte_id = Column(String(20), ForeignKey('cohortes.id', ondelete='CASCADE'), nullable=False)
    niveau_actuel = Column(Integer, nullable=False, default=1)
    sous_groupe = Column(String(5), nullable=False, default='A')  # A, B, C, etc.
    examens_reussis = Column(Integer, nullable=False, default=0)
    date_inscription = Column(DateTime, nullable=False, default=datetime.now)
    discord_role_id = Column(BigInteger, nullable=True)  # ID du rôle Discord assigné
    discord_channel_id = Column(BigInteger, nullable=True)  # ID du salon Discord privé

    # Relations
    cohorte = relationship("Cohorte", back_populates="utilisateurs")
    reviews = relationship("Review", back_populates="utilisateur", cascade="all, delete-orphan")
    exam_results = relationship("ExamResult", back_populates="utilisateur", cascade="all, delete-orphan")
    historique = relationship("HistoriqueCohorte", back_populates="utilisateur", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("niveau_actuel BETWEEN 1 AND 5", name='chk_niveau'),
    )

    def __repr__(self):
        return f"<Utilisateur {self.username} - Niveau {self.niveau_actuel}{self.sous_groupe}>"


class DiscordGroup(Base):
    """Table des groupes Discord (rôles et salons)"""
    __tablename__ = 'discord_groups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    niveau = Column(Integer, nullable=False)  # 1, 2, 3, 4, 5
    sous_groupe = Column(String(5), nullable=False)  # A, B, C, etc.
    role_id = Column(BigInteger, nullable=False, unique=True)  # ID du rôle Discord
    channel_id = Column(BigInteger, nullable=False, unique=True)  # ID du salon Discord
    max_membres = Column(Integer, nullable=False, default=15)
    date_creation = Column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("niveau BETWEEN 1 AND 5", name='chk_niveau_group'),
    )

    def __repr__(self):
        return f"<DiscordGroup Niveau-{self.niveau}{self.sous_groupe}>"


class CalendrierExamen(Base):
    """Table du calendrier des examens par cohorte"""
    __tablename__ = 'calendrier_examens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cohorte_id = Column(String(20), ForeignKey('cohortes.id', ondelete='CASCADE'), nullable=False)
    niveau = Column(Integer, nullable=False)
    exam_id = Column(Integer, nullable=False)  # Référence vers exam.json
    date_debut = Column(DateTime, nullable=False)  # Début de la tranche horaire (6h)
    date_fin = Column(DateTime, nullable=False)  # Fin de la tranche horaire

    # Relations
    cohorte = relationship("Cohorte", back_populates="calendrier")

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
        return f"<HistoriqueCohorte user={self.user_id} cohorte={self.cohorte_id}>"


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

    def __repr__(self):
        return f"<Review user={self.user_id} question={self.question_id}>"


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
        return f"<ExamResult user={self.user_id} exam={self.exam_id} score={self.score}/{self.total}>"
