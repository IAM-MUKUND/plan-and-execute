import sys
import os

# Add CAT-1 to python path so backend package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq import Groq
from backend.tools.key_manager import key_manager

def main():
    print("=== Groq Smoke Test with KeyManager ===")
    print(f"Loaded {len(key_manager.groq_keys)} Groq API keys.")
    print(f"Current active key index: {key_manager.groq_index}")

    def _groq_completion(api_key: str):
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": "Respond with a single sentence confirming Groq API connection is working."}
            ],
            max_tokens=50
        )
        return response.choices[0].message.content.strip()

    try:
        result = key_manager.execute_groq(_groq_completion)
        print("\n[SUCCESS] Groq API Response:")
        print(f"--> {result}")
    except Exception as e:
        print(f"\n[FAILURE] Groq API call failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
