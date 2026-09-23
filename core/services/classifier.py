import os
import json
import logging
from google import genai
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

logger = logging.getLogger(__name__)

class ClassifierEsse3:
    def __init__(self, filepath='mapping_rules.json'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.rules = self._load_rules(os.path.join(current_dir, filepath))
        self.valid_categories = list(self.rules.keys())
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            logger.warning("ATTENZIONE: La variabile GEMINI_API_KEY non è stata trovata. Controlla il file .env!")
        else:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("INFO: Chiave API caricata con successo dal file .env.")


    def _load_rules(self, filepath):
        if not os.path.exists(filepath):
            return {}
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    # def classify(self, title):
    #     if not title:
    #         return "Da non considerare", "Errore"
    #
    #     title_lower = title.lower()
    #     found_categories = []
    #
    #     for category, words in self.rules.items():
    #         for word in words:
    #             if word in title_lower:
    #                 if category not in found_categories:
    #                     found_categories.append(category)
    #                 break
    #
    #     if len(found_categories) == 1:
    #         return found_categories[0], "JSON (Locale)"
    #
    #     return self._ask_to_gemini(title), "IA (Gemini)"


    def classify(self, title):
        if not title or title == "Senza Titolo":
            return "Da non considerare", "Errore (Titolo vuoto)"

        title_lower = title.lower()

        scores = {}

        for category, words in self.rules.items():
            score = 0
            for word in words:
                if word in title_lower:
                    score += 1

            if score > 0:
                scores[category] = score

        if not scores:
            resp = self._ask_to_gemini(title)
            #resp = "Da non considerare"
            logger.info(f"INFO: l'evento {title} è stato classificato come {resp}")
            return resp, "IA (Nessun match)"

        max_score = max(scores.values())

        vincitori = [cat for cat, punti in scores.items() if punti == max_score]

        if len(vincitori) == 1:
            return vincitori[0], f"JSON (Conteggio: {max_score} parole)"

        return self._ask_to_gemini(title), f"IA (Spareggio tra {len(vincitori)} categorie)"
        #return "Da non considerare", f"IA (Spareggio tra {len(vincitori)} categorie)"



    def _ask_to_gemini(self, title):
        if not self.api_key:
            return "Da non considerare"

        formatted_categories = "\n".join(f"- {cat}" for cat in self.valid_categories)
        prompt = f"""
            Sei un assistente per la classificazione di eventi accademici per il registro universitario Esse3.
            Devi classificare il seguente titolo di un evento in UNA SOLA delle categorie disponibili.

            Categorie universitarie ammesse:
{formatted_categories}
            - Da non considerare (USA QUESTA CATEGORIA per eventi personali, impegni privati, tempo libero, o qualsiasi evento che non appartenga chiaramente a una delle mansioni universitarie sopra elencate).

            Titolo evento: "{title}"

            Rispondi SOLO con il nome esatto della categoria (una di quelle universitarie oppure "Da non considerare"), senza virgolette, spiegazioni o punteggiatura extra.
            Se l'evento non è pertinente alle categorie universitarie indicate o se non è possibile dedurre con chiarezza la categoria, rispondi con "Da non considerare".
            """

        try:
            # client = genai.Client(api_key=self.api_key)
            # chat = client.chats.create(model='gemini-3.5-flash')
            # response = chat.send_message(prompt)
            response = self.client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            cleaned_response = response.text.strip().strip('"\'')
            allowed_categories = {cat.lower(): cat for cat in self.valid_categories}
            allowed_categories["da non considerare"] = "Da non considerare"

            cleaned_lower = cleaned_response.lower()
            if cleaned_lower in allowed_categories:
                return allowed_categories[cleaned_lower]

            logger.warning(f"Risposta Gemini '{cleaned_response}' non riconosciuta, impostato 'Da non considerare'")
            return "Da non considerare"

        except Exception as e:
            logger.error(f"ERRORE GEMINI: {e}")
            return "Da non considerare"