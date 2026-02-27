from openai import OpenAI, AzureOpenAI
import kb_agent.config as config

class LLMClient:
    def __init__(self):
        settings = config.settings
        if not settings:
            raise ValueError("Settings not initialized.")

        # Determine if Azure or OpenAI based on URL or other settings if needed.
        # For now, assume generic OpenAI-compatible client.
        self.client = OpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=str(settings.llm_base_url)
        )

        # Sanitize model name for Groq compatibility
        # Groq API expects just the model name without prefixes like 'groq-com/' or 'groq/'
        model_name = settings.llm_model
        if model_name.startswith("groq-com/"):
            model_name = model_name.removeprefix("groq-com/")
        elif model_name.startswith("groq/"):
            model_name = model_name.removeprefix("groq/")

        self.model = model_name

    def chat_completion(self, messages: list, temperature: float = 0.0) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback or log error
            print(f"LLM Error: {e}")
            return "Error generating response."

    def generate_summary(self, content: str) -> str:
        """Specific helper for generating summaries."""
        prompt = f"Please provide a concise summary of the following document. Focus on key entities, decisions, and outcomes:\n\n{content[:4000]}" # Truncate for safety
        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes technical documents."},
            {"role": "user", "content": prompt}
        ]
        return self.chat_completion(messages)
