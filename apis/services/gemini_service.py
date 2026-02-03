import re
from google import genai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class GeminiAIService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash"  # Current stable
        self.fallback_model = "gemini-2.0-flash"

    def get_prompt_template(self, language='english'):
        """
        Enhanced Prompt Engineering:
        - Enforces 'HTML Fragment' output (No <html>, <head>, <body>).
        - Adds specific CSS classes for frontend styling hooks.
        - Preserves your domain logic for BharatAbhiyan.
        """
        
        base_context = """You are an AI expert for BharatAbhiyan, an Indian government services platform.

MISSION:
Provide a precise, actionable guide for government schemes.

OUTPUT FORMAT RULES (CRITICAL):
1. Return **ONLY HTML Body Content**.
2. **DO NOT** use `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`, or `<style>` tags.
3. **DO NOT** use Markdown code blocks (```html).
4. Start directly with the main heading `<h2>`.
5. Use semantic HTML5 tags: `<h2>`, `<h3>`, `<p>`, `<ul>`, `<ol>`, `<li>`, `<strong>`, `<a>`.
6. Use these specific CSS classes for styling hooks:
   - `<div class="scheme-highlight">` for key info/overview.
   - `<ul class="check-list">` for eligibility.
   - `<div class="alert-box">` for critical deadlines/notes.

CONTENT STRUCTURE:
1. **Overview:** Brief 2-line summary.
2. **Eligibility:** Bulleted list of who can apply.
3. **Documents Required:** Checklist of mandatory proofs.
4. **Application Process:** Numbered, step-by-step actionable instructions.
5. **Official Links:** Direct `<a href="...">` links to portals (must use target="_blank")."""

        language_instructions = {
            'english': "\n\nLanguage: Respond in professional, simple English.",
            'hindi': "\n\nLanguage: Respond in clear Hindi (Devanagari). Use English for technical terms (e.g., 'OTP', 'Captcha')."
        }
        
        return base_context + language_instructions.get(language.lower(), language_instructions['english'])
    
    def format_user_query(self, question, language='english'):
        prompt_template = self.get_prompt_template(language)
        return f"""{prompt_template}

USER QUERY: {question}

Generate the HTML guide now:"""

    def _clean_response(self, text):
        """
        Sanitizes AI output to ensure clean HTML fragments.
        Removes Markdown, full-page wrappers, and excessive newlines.
        """
        if not text: 
            return ""

        # 1. Remove Markdown code blocks (```html ... ```)
        text = re.sub(r'^```html\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'```$', '', text)

        # 2. Remove full HTML document structure if the AI hallucinates it
        # (This removes <!DOCTYPE>, <html>, <head>, <body> and their closing tags)
        text = re.sub(r'<!DOCTYPE html>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<html.*?>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'</html>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<head>.*?</head>', '', text, flags=re.IGNORECASE | re.DOTALL) # Remove head/styles completely
        text = re.sub(r'<body.*?>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'</body>', '', text, flags=re.IGNORECASE)

        # 3. Collapse multiple newlines into a single newline to fix "extra \n\n\n"
        text = re.sub(r'\n\s*\n', '\n', text)

        return text.strip()

    def _generate(self, model, prompt, config):
        return self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=config
        )

    def get_ai_guide(self, question, language='english'):
        formatted_prompt = self.format_user_query(question, language)
        
        # Optimized config for factual guides
        generation_config = types.GenerateContentConfig(
            temperature=0.3, # Lower temperature = more precise formatting
            top_p=0.8,
            max_output_tokens=2048,
        )
        
        try:
            # Try Primary
            response = self._generate(self.model_name, formatted_prompt, generation_config)
        except Exception as e:
            logger.warning(f"Primary model failed: {e}. Trying fallback.")
            try:
                # Try Fallback
                response = self._generate(self.fallback_model, formatted_prompt, generation_config)
            except Exception as e2:
                return {'success': False, 'message': f'AI Service Unavailable: {str(e2)}'}

        if not response or not response.text:
            return {'success': False, 'message': 'Empty response from AI'}
        
        # Clean the response
        cleaned_html = self._clean_response(response.text)
        
        # Wrap in a scoped class for your frontend
        final_html = f'<div class="bharatabhiyan-ai-content">{cleaned_html}</div>'
        
        return {
            'success': True,
            'response': final_html,
            'language': language
        }