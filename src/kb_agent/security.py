import re

class Security:
    # Regex for 16 digit card numbers, allowing dashes or spaces.
    # Matches: 1234123412341234, 1234-1234-1234-1234, 1234 1234 1234 1234
    CARD_REGEX = re.compile(r'\b(?:\d{4}[- ]?){3}\d{4}\b')

    @classmethod
    def mask_sensitive_data(cls, text: str) -> str:
        """
        Masks 16-digit credit card numbers with 'XXXX-XXXX-XXXX-XXXX'.
        """
        if not text:
            return ""

        def replace(match):
            # We could do Luhn check here for higher precision, but simple regex is usually fine for masking.
            return "XXXX-XXXX-XXXX-XXXX"

        return cls.CARD_REGEX.sub(replace, text)
