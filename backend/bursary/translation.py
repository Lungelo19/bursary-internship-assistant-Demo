"""
Translation layer for the Bursary and Internship Assistant.

This module:
    1. Detects the user's language.
    2. Translates non-English input into English.
    3. Translates the AI's English response back into
       the user's original language.

Google Cloud Translation Basic v2 is used.
"""

from pathlib import Path
import html
import os

import requests
from dotenv import load_dotenv


# =========================================================
# 1. LOAD ENVIRONMENT VARIABLES
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[1]

ENV_FILE = BASE_DIR / ".env"

load_dotenv(
    ENV_FILE,
    override=True,
)


GOOGLE_TRANSLATE_API_KEY = os.environ.get(
    "GOOGLE_TRANSLATE_API_KEY",
    "",
).strip()


# =========================================================
# 2. GOOGLE TRANSLATION API
# =========================================================

TRANSLATE_URL = (
    "https://translation.googleapis.com/"
    "language/translate/v2"
)


# =========================================================
# 3. CUSTOM ERROR
# =========================================================

class TranslationError(Exception):
    """
    Raised when Google Translation fails.
    """

    pass


# =========================================================
# 4. INTERNAL TRANSLATION FUNCTION
# =========================================================

def _translate(
    text,
    target_language,
    source_language=None,
):
    """
    Send text to Google Cloud Translation.

    If source_language is None,
    Google automatically detects the language.

    Returns:

        {
            "translated_text": "...",
            "detected_language": "zu"
        }
    """

    if not text or not text.strip():

        return {
            "translated_text": text,
            "detected_language":
                source_language or "en",
        }


    if not GOOGLE_TRANSLATE_API_KEY:

        raise TranslationError(
            "GOOGLE_TRANSLATE_API_KEY "
            "is missing from the .env file."
        )


    payload = {
        "q": text,
        "target": target_language,
        "format": "text",
    }


    if source_language:

        payload["source"] = (
            source_language
        )


    headers = {
        "X-goog-api-key":
            GOOGLE_TRANSLATE_API_KEY,

        "Content-Type":
            "application/json",
    }


    try:

        response = requests.post(
            TRANSLATE_URL,
            headers=headers,
            json=payload,
            timeout=15,
        )

    except requests.RequestException as error:

        raise TranslationError(
            "Could not connect to "
            "Google Cloud Translation: "
            f"{error}"
        ) from error


    if not response.ok:

        raise TranslationError(
            "Google Translation request failed: "
            f"{response.status_code} - "
            f"{response.text}"
        )


    try:

        data = response.json()

        translation = (
            data["data"]
            ["translations"][0]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as error:

        raise TranslationError(
            "Google returned an unexpected "
            "translation response."
        ) from error


    translated_text = html.unescape(
        translation.get(
            "translatedText",
            text,
        )
    )


    detected_language = translation.get(
        "detectedSourceLanguage",
        source_language,
    )


    return {
        "translated_text":
            translated_text,

        "detected_language":
            detected_language,
    }


# =========================================================
# 5. USER INPUT -> ENGLISH
# =========================================================

def translate_to_english(text):
    """
    Detect the language of the user's message.

    If it is not English,
    translate it into English.

    Returns:

        english_text, detected_language


    Example:

        Input:
            Ngidinga umfundaze

        Output:
            (
                "I need a scholarship.",
                "zu"
            )
    """

    result = _translate(
        text=text,
        target_language="en",
    )


    detected_language = (
        result.get(
            "detected_language"
        )
        or "en"
    )


    detected_language = (
        detected_language
        .strip()
        .lower()
    )


    # Already English
    if detected_language == "en":

        return text, "en"


    return (
        result["translated_text"],
        detected_language,
    )


# =========================================================
# 6. ENGLISH RESPONSE -> USER LANGUAGE
# =========================================================

def translate_from_english(
    text,
    target_language,
):
    """
    Translate the AI's English response
    back into the user's original language.
    """

    if not text:

        return text


    if not target_language:

        return text


    target_language = (
        target_language
        .strip()
        .lower()
    )


    # No translation needed
    if target_language == "en":

        return text


    result = _translate(
        text=text,
        source_language="en",
        target_language=target_language,
    )


    return result[
        "translated_text"
    ]


# =========================================================
# 7. STANDALONE TEST
# =========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("GOOGLE TRANSLATION TEST")
    print("=" * 60)


    user_text = input(
        "Enter a message: "
    ).strip()


    try:

        english_text, language = (
            translate_to_english(
                user_text
            )
        )


        print(
            "\nDetected language:",
            language,
        )


        print(
            "English:",
            english_text,
        )


        test_response = (
            "I found some bursaries "
            "that may be relevant "
            "to your studies."
        )


        translated_response = (
            translate_from_english(
                test_response,
                language,
            )
        )


        print(
            "\nResponse in user's language:",
            translated_response,
        )


    except TranslationError as error:

        print(
            "\nTranslation error:",
            error,
        )