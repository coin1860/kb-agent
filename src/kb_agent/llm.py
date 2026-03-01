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

    def chat_completion(self, messages: list, temperature: float = 0.2) -> str:
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
        """Specific helper for generating summaries, with Map-Reduce for large docs."""
        if len(content) <= 4000:
            return self._summarize_text(content)
            
        # Map Phase: chunk and summarize each
        from kb_agent.chunking import MarkdownAwareChunker
        chunker = MarkdownAwareChunker(max_chars=4000, overlap_chars=200)
        chunks = chunker.chunk(content, {})
        
        sub_summaries = []
        for i, c in enumerate(chunks):
            sub_sum = self._summarize_text(c.text, context=f"Part {i+1} of {len(chunks)}")
            sub_summaries.append(f"--- Part {i+1} Summary ---\n{sub_sum}")
            
        # Reduce Phase: combine sub summaries
        combined = "\n\n".join(sub_summaries)
        
        reduce_prompt = f"The following are summaries of different parts of a large document. Please merge them into a single, cohesive, and comprehensive global summary. Focus on key entities, decisions, and overall outcomes:\n\n{combined[:30000]}" # Safety bound for huge files
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that synthesizes multiple document summaries into one cohesive global summary."},
            {"role": "user", "content": reduce_prompt}
        ]
        return self.chat_completion(messages)

    def _summarize_text(self, text: str, context: str = "") -> str:
        prompt = f"Please provide a concise summary of the following document text. Focus on key entities, decisions, and outcomes:\n\n{text}"
        if context:
            prompt = f"Context: {context}\n\n{prompt}"
            
        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes technical documents."},
            {"role": "user", "content": prompt}
        ]
        return self.chat_completion(messages)
