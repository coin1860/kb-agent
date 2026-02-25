from kb_agent.security import Security

def test_masking():
    cases = [
        ("1234-5678-9012-3456", "XXXX-XXXX-XXXX-XXXX"),
        ("1234 5678 9012 3456", "XXXX-XXXX-XXXX-XXXX"),
        ("1234567890123456", "XXXX-XXXX-XXXX-XXXX"),
        ("Text 1234-5678-9012-3456 end", "Text XXXX-XXXX-XXXX-XXXX end"),
        ("No sensitive data", "No sensitive data")
    ]

    for input_text, expected in cases:
        result = Security.mask_sensitive_data(input_text)
        if result != expected:
            print(f"FAILED: '{input_text}' -> '{result}', expected '{expected}'")
        else:
            print(f"PASSED: '{input_text}'")

if __name__ == "__main__":
    test_masking()
