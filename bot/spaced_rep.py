from datetime import datetime, timedelta

class SpacedRepetition:
    """Implémentation de l'algorithme SM-2 pour la révision espacée"""
    
    def __init__(self):
        self.default_ef = 2.5  # Easiness Factor par défaut
        self.min_ef = 1.3      # EF minimum
        self.first_interval_correct = 2  # Jours si première réponse correcte
        self.first_interval_incorrect = 10 / (60 * 24)  # 10 minutes en jours
    
    def calculate_first_review(self, user_id, question_id, quality):
        """
        Calcule la première révision pour une nouvelle question
        quality: 0 (incorrect) ou 5 (correct)
        """
        if quality >= 3:  # Réponse correcte
            interval_days = self.first_interval_correct
            repetitions = 1
            ef = self.default_ef
        else:  # Réponse incorrecte
            interval_days = self.first_interval_incorrect
            repetitions = 0
            ef = self._calculate_ef(self.default_ef, quality)
        
        next_review = datetime.now() + timedelta(days=interval_days)
        
        return {
            'user_id': user_id,
            'question_id': question_id,
            'next_review': next_review,
            'interval': interval_days,
            'repetitions': repetitions,
            'easiness_factor': ef
        }
    
    def update_review(self, review_data, quality):
        """
        Met à jour une révision existante selon SM-2
        review_data: dict contenant les données de révision actuelles
        quality: 0-5 (0 = oublié, 5 = parfait)
        """
        ef = review_data['easiness_factor']
        repetitions = review_data['repetitions']
        interval = review_data['interval']
        
        # Mise à jour de l'Easiness Factor
        new_ef = self._calculate_ef(ef, quality)
        
        if quality < 3:  # Réponse incorrecte - reset
            new_repetitions = 0
            new_interval = self.first_interval_incorrect  # 10 minutes
        else:  # Réponse correcte
            new_repetitions = repetitions + 1
            
            if new_repetitions == 1:
                new_interval = self.first_interval_correct  # 2 jours
            else:
                # Intervalle suivant = intervalle précédent × 2.5 (comme spécifié)
                new_interval = interval * 2.5
        
        next_review = datetime.now() + timedelta(days=new_interval)
        
        return {
            'user_id': review_data['user_id'],
            'question_id': review_data['question_id'],
            'next_review': next_review,
            'interval': new_interval,
            'repetitions': new_repetitions,
            'easiness_factor': new_ef
        }
    
    def _calculate_ef(self, current_ef, quality):
        """
        Calcule le nouvel Easiness Factor selon la formule SM-2
        EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        """
        new_ef = current_ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        
        # L'EF ne peut pas descendre en dessous de 1.3
        if new_ef < self.min_ef:
            new_ef = self.min_ef
        
        return round(new_ef, 2)
