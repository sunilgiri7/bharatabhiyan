# services/gemini_service.py

import google.generativeai as genai
from django.conf import settings


class GeminiAIService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def get_prompt_template(self, language='english'):
        """Get domain-specific prompt template based on language"""
        
        base_context = """You are an AI assistant for BharatAbhiyan - a platform connecting citizens with service providers and government schemes in India.

Your role is to guide users about:
1. Government schemes and services (primary focus)
2. How to apply for various government benefits
3. Eligibility criteria and required documents
4. Step-by-step application processes
5. Official government portals and resources

CRITICAL RESPONSE RULES:
- Provide accurate, structured information about Indian government schemes
- Include official reference links to government portals (.gov.in, .nic.in domains)
- Use proper HTML formatting for clean display
- Keep responses concise yet comprehensive (300-800 words)
- Focus on actionable steps and practical guidance
- Always cite official sources

HTML FORMATTING REQUIREMENTS:
- Use <h2> for main headings
- Use <h3> for sub-headings
- Use <p> for paragraphs
- Use <ul> and <li> for unordered lists
- Use <ol> and <li> for ordered/step-by-step lists
- Use <a href="URL" target="_blank" rel="noopener noreferrer"> for hyperlinks
- Use <strong> for emphasis on important points
- Use <div class="info-box"> for highlighting key information

HYPERLINK GUIDELINES:
- Only include verified, official government website links
- Prefer .gov.in and .nic.in domains
- Include direct application portal links when available
- Add scheme-specific helpline numbers when relevant"""

        language_instructions = {
            'english': "\n\nRespond in clear, simple English.",
            'hindi': "\n\nRespond in clear Hindi (Devanagari script). Use simple Hindi words that common people can understand. Translate technical terms but keep scheme names in original English/Hindi as officially used."
        }
        
        return base_context + language_instructions.get(language.lower(), language_instructions['english'])
    
    def format_user_query(self, question, language='english'):
        """Format the complete prompt with user question"""
        
        prompt_template = self.get_prompt_template(language)
        
        formatted_prompt = f"""{prompt_template}

USER QUESTION: {question}

RESPONSE FORMAT:
Provide a well-structured response with:
1. Brief overview (1-2 sentences)
2. Eligibility criteria (if applicable)
3. Required documents (if applicable)
4. Step-by-step application process
5. Official reference links
6. Important notes/deadlines (if applicable)

Remember to format the entire response in proper HTML as specified above."""
        
        return formatted_prompt
    
    def get_ai_guide(self, question, language='english'):
        try:
            formatted_prompt = self.format_user_query(question, language)
            
            # Configure generation parameters
            generation_config = {
                'temperature': 0.4,  # more factual responses
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,
            }
            
            # Generate response
            response = self.model.generate_content(
                formatted_prompt,
                generation_config=generation_config
            )
            
            # Extract and clean the response
            ai_response = response.text.strip()
            
            # Wrap in container div if not already wrapped
            if not ai_response.startswith('<div'):
                ai_response = f'<div class="BharatAbhiyan-AI-Guide-Response">{ai_response}</div>'
            
            return {
                'success': True,
                'response': ai_response,
                'language': language
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to generate AI response'
            }