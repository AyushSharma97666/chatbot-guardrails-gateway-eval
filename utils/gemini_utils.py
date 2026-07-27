"""
Gemini API Utility using the new google.genai package
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from utils.logger import get_logger

logger = get_logger("gemini_utils")


def _extract_usage(response) -> Dict[str, Any]:
    """Best-effort token usage extraction — used by chat_gateway.py to
    populate the audit log's cost/latency tracking. Returns an empty dict
    if the SDK response has no usage_metadata (e.g. on some error paths)."""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", None),
        "completion_tokens": getattr(usage, "candidates_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
    }


class GeminiClient:
    """Client for interacting with Google's Gemini API using new SDK"""
    
    def __init__(self, api_key: str = None, model_name: str = None):
        """
        Initialize Gemini client with new SDK
        
        Args:
            api_key (str): Google API key (if None, will get from config)
            model_name (str): Gemini model to use (default: from config or "gemini-2.0-flash-exp")
        """
        # Get API key from config if not provided
        if api_key is None:
            api_key = config.GEMINI_API_KEY
        
        # Get model name from config if not provided
        if model_name is None:
            model_name = getattr(config, 'GEMINI_MODEL', "gemini-2.0-flash-exp")
        
        logger.info(f"Initializing GeminiClient with model: {model_name}")
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            logger.error("API key not found or invalid")
            raise ValueError("API key not found. Please set GOOGLE_API_KEY in config.py or .env file")
        logger.debug("GeminiClient initialized successfully")
        
        # Initialize the new client
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.chat_history = []
        self.system_prompt_folder = getattr(config, 'PROMPTS_FOLDER', "prompts/system_prompts")
    
    def load_system_prompt(self, prompt_name: str = "default") -> str:
        """
        Load system prompt from file
        
        Args:
            prompt_name (str): Name of the prompt file (without .txt extension)
        
        Returns:
            str: System prompt content
        """
        prompt_path = Path(self.system_prompt_folder) / f"{prompt_name}.txt"
        logger.info(f"Loading system prompt: {prompt_path}")
        
        if not prompt_path.exists():
            logger.error(f"System prompt file not found: {prompt_path}")
            raise FileNotFoundError(f"System prompt file not found: {prompt_path}")
        
        with open(prompt_path, 'r', encoding='utf-8') as file:
            prompt_content = file.read()
        
        logger.debug(f"Loaded prompt ({len(prompt_content)} chars)")
        return prompt_content
    
    def list_available_prompts(self) -> List[str]:
        """List all available system prompts in the prompts folder"""
        prompt_dir = Path(self.system_prompt_folder)
        if not prompt_dir.exists():
            return []
        
        prompts = [f.stem for f in prompt_dir.glob("*.txt")]
        return prompts
    
    def generate_response(self, user_input: str, system_prompt: str = None, 
                          prompt_name: str = "default", 
                          temperature: float = None,
                          max_output_tokens: int = None) -> Dict[str, Any]:
        logger.info(f"Generating response | prompt: {prompt_name} | input: {user_input[:80]}...")
        if temperature is None:
            temperature = getattr(config, 'TEMPERATURE', 0.7)
        if max_output_tokens is None:
            max_output_tokens = getattr(config, 'MAX_OUTPUT_TOKENS', 2048)
        
        try:
            if system_prompt:
                prompt_content = system_prompt
            else:
                prompt_content = self.load_system_prompt(prompt_name)
            
            full_prompt = f"{prompt_content}\n\nUser: {user_input}\n\nAssistant:"
            logger.debug(f"Full prompt length: {len(full_prompt)} chars")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            )
            
            logger.info(f"Response generated ({len(response.text)} chars)")
            return {
                'success': True,
                'text': response.text,
                'prompt_used': prompt_name,
                'user_input': user_input,
                'usage': _extract_usage(response),
                'error': None
            }

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return {
                'success': False,
                'text': None,
                'prompt_used': prompt_name,
                'user_input': user_input,
                'usage': {},
                'error': str(e)
            }

    def start_chat_session(self, system_prompt: str = None, prompt_name: str = "default"):
        logger.info(f"Starting chat session | prompt: {prompt_name}")
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = self.load_system_prompt(prompt_name)
        
        self.prompt_name = prompt_name
        self.chat_history = []
        logger.debug("Chat session started")
        return self
    
    def send_chat_message(self, user_input: str, temperature: float = None) -> Dict[str, Any]:
        if not hasattr(self, 'system_prompt'):
            logger.error("send_chat_message called without active session")
            raise ValueError("No active chat session. Call start_chat_session() first.")
        
        logger.info(f"Chat message | input: {user_input[:80]}...")
        if temperature is None:
            temperature = getattr(config, 'TEMPERATURE', 0.7)
        
        try:
            messages = [{"role": "user", "content": user_input}]
            full_prompt = f"{self.system_prompt}\n\n"
            for msg in self.chat_history:
                full_prompt += f"{msg['role']}: {msg['content']}\n"
            full_prompt += f"User: {user_input}\nAssistant:"
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(temperature=temperature)
            )
            
            self.chat_history.append({"role": "user", "content": user_input})
            self.chat_history.append({"role": "assistant", "content": response.text})
            
            logger.debug("Chat response stored in history")
            return {
                'success': True,
                'text': response.text,
                'user_input': user_input,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Chat message failed: {e}")
            return {
                'success': False,
                'text': None,
                'user_input': user_input,
                'error': str(e)
            }
    
    def generate_with_context(self, user_input: str, context: str, 
                             system_prompt: str = None, 
                             prompt_name: str = "default") -> Dict[str, Any]:
        logger.info(f"generate_with_context | prompt: {prompt_name} | context: {len(context)} chars")
        try:
            if system_prompt:
                prompt_content = system_prompt
            else:
                prompt_content = self.load_system_prompt(prompt_name)
            
            full_prompt = f"{prompt_content}\n\nContext: {context}\n\nUser: {user_input}\n\nAssistant:"
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            
            logger.info("Context response generated successfully")
            return {
                'success': True,
                'text': response.text,
                'prompt_used': prompt_name,
                'user_input': user_input,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"generate_with_context failed: {e}")
            return {
                'success': False,
                'text': None,
                'prompt_used': prompt_name,
                'user_input': user_input,
                'error': str(e)
            }


    def generate_chatbot_response(self, user_input: str, query_result: Optional[Dict] = None,
                                  prompt_name: str = "chatbot") -> Dict[str, Any]:
        logger.info(f"Chatbot response | input: {user_input[:80]}...")
        try:
            prompt_content = self.load_system_prompt(prompt_name)
            context = ""

            if query_result and query_result.get('success') and query_result.get('data'):
                data = query_result['data']
                columns = query_result['columns']
                row_count = query_result.get('row_count', len(data))

                import pandas as pd
                df = pd.DataFrame(data, columns=columns)
                context = f"Query returned {row_count} row(s).\n\nColumns: {', '.join(columns)}\n\nData preview:\n{df.head(20).to_string(index=False)}"
                logger.debug(f"Context built: {row_count} rows, {len(columns)} columns")
            elif query_result and not query_result.get('success'):
                context = f"No data available. Error: {query_result.get('error', 'Unknown error')}"
                logger.warning(f"Query result had error: {query_result.get('error')}")
            else:
                context = "No query was executed."
                logger.debug("No query result provided")

            full_prompt = f"{prompt_content}\n\nQuery Results:\n{context}\n\nUser Question: {user_input}\n\nAssistant:"
            logger.debug(f"Chatbot prompt length: {len(full_prompt)} chars")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    max_output_tokens=1024,
                )
            )

            logger.info("Chatbot response generated successfully")
            return {
                'success': True,
                'text': response.text,
                'user_input': user_input,
                'usage': _extract_usage(response),
                'error': None
            }

        except Exception as e:
            logger.error(f"Chatbot response failed: {e}")
            return {
                'success': False,
                'text': None,
                'user_input': user_input,
                'usage': {},
                'error': str(e)
            }


# Convenience functions for easy use

def get_gemini_response(user_input: str, prompt_name: str = "default", 
                       api_key: str = None, **kwargs) -> Dict[str, Any]:
    logger.info(f"get_gemini_response | prompt: {prompt_name} | input: {user_input[:60]}...")
    try:
        client = GeminiClient(api_key=api_key)
        return client.generate_response(user_input, prompt_name=prompt_name, **kwargs)
    except Exception as e:
        logger.error(f"get_gemini_response failed: {e}")
        return {
            'success': False,
            'text': None,
            'prompt_used': prompt_name,
            'user_input': user_input,
            'error': str(e)
        }


def generate_chatbot_response(user_input: str, query_result: Optional[Dict] = None,
                              prompt_name: str = "chatbot", api_key: str = None) -> Dict[str, Any]:
    logger.info(f"generate_chatbot_response | prompt: {prompt_name}")
    try:
        client = GeminiClient(api_key=api_key)
        return client.generate_chatbot_response(user_input, query_result, prompt_name)
    except Exception as e:
        logger.error(f"generate_chatbot_response failed: {e}")
        return {
            'success': False,
            'text': None,
            'user_input': user_input,
            'error': str(e)
        }


def extract_sql_from_response(response_text: str) -> str:
    logger.debug("Extracting SQL from response text")
    import re

    sql_pattern = r"```sql\n(.*?)\n```"
    matches = re.findall(sql_pattern, response_text, re.DOTALL)

    if matches:
        sql = matches[0].strip()
        logger.debug(f"SQL extracted from code block ({len(sql)} chars)")
        return sql

    # Read-only fallback only — deliberately excludes INSERT/UPDATE/DELETE/
    # CREATE/ALTER/DROP so this extraction path can never hand back a write
    # statement even before utils.sql_guardrail gets a chance to validate it.
    sql_keywords = ['SELECT', 'WITH']
    lines = response_text.split('\n')
    sql_lines = []

    for line in lines:
        if any(line.strip().upper().startswith(keyword) for keyword in sql_keywords):
            sql_lines.append(line.strip())

    if sql_lines:
        sql = ' '.join(sql_lines)
        logger.debug(f"SQL extracted from keyword lines ({len(sql)} chars)")
        return sql

    logger.warning("No SQL found in response")
    return None


# """
# Gemini API Utility for handling system prompts and generating responses
# """

# import os
# import google.generativeai as genai

# from pathlib import Path
# from typing import Optional, Dict, Any, List
# import json

# class GeminiClient:
#     """Client for interacting with Google's Gemini API"""
    
#     def __init__(self, api_key: str = None, model_name: str = "gemini-pro"):
#         """
#         Initialize Gemini client
        
#         Args:
#             api_key (str): Google API key (if None, will look for GOOGLE_API_KEY env variable)
#             model_name (str): Gemini model to use (default: gemini-pro)
#         """
#         # Set API key
#         if api_key:
#             genai.configure(api_key=api_key)
#         else:
#             # Try to get from environment variable
#             api_key = os.getenv("GOOGLE_API_KEY")
#             if api_key:
#                 genai.configure(api_key=api_key)
#             else:
#                 raise ValueError("API key must be provided or set as GOOGLE_API_KEY environment variable")
        
#         self.model = genai.GenerativeModel(model_name)
#         self.chat = None
#         self.system_prompt_folder = "prompts/system_prompts"
    
#     def load_system_prompt(self, prompt_name: str = "default") -> str:
#         """
#         Load system prompt from file
        
#         Args:
#             prompt_name (str): Name of the prompt file (without .txt extension)
        
#         Returns:
#             str: System prompt content
#         """
#         prompt_path = Path(self.system_prompt_folder) / f"{prompt_name}.txt"
        
#         if not prompt_path.exists():
#             raise FileNotFoundError(f"System prompt file not found: {prompt_path}")
        
#         with open(prompt_path, 'r', encoding='utf-8') as file:
#             prompt_content = file.read()
        
#         return prompt_content
    
#     def list_available_prompts(self) -> List[str]:
#         """List all available system prompts in the prompts folder"""
#         prompt_dir = Path(self.system_prompt_folder)
#         if not prompt_dir.exists():
#             return []
        
#         prompts = [f.stem for f in prompt_dir.glob("*.txt")]
#         return prompts
    
#     def generate_response(self, user_input: str, system_prompt: str = None, 
#                           prompt_name: str = "default", 
#                           temperature: float = 0.7,
#                           max_output_tokens: int = 2048) -> Dict[str, Any]:
#         """
#         Generate response using Gemini with system prompt
        
#         Args:
#             user_input (str): User's input/question
#             system_prompt (str): System prompt to use (if provided, overrides prompt_name)
#             prompt_name (str): Name of system prompt file to use
#             temperature (float): Controls randomness (0.0 to 1.0)
#             max_output_tokens (int): Maximum tokens in response
        
#         Returns:
#             dict: Response containing text and metadata
#         """
#         try:
#             # Load system prompt
#             if system_prompt:
#                 prompt_content = system_prompt
#             else:
#                 prompt_content = self.load_system_prompt(prompt_name)
            
#             # Combine system prompt with user input
#             full_prompt = f"{prompt_content}\n\nUser: {user_input}\n\nAssistant:"
            
#             # Generate response
#             response = self.model.generate_content(
#                 full_prompt,
#                 generation_config=genai.types.GenerationConfig(
#                     temperature=temperature,
#                     max_output_tokens=max_output_tokens,
#                 )
#             )
            
#             return {
#                 'success': True,
#                 'text': response.text,
#                 'prompt_used': prompt_name,
#                 'user_input': user_input,
#                 'error': None
#             }
            
#         except Exception as e:
#             return {
#                 'success': False,
#                 'text': None,
#                 'prompt_used': prompt_name,
#                 'user_input': user_input,
#                 'error': str(e)
#             }
    
#     def start_chat_session(self, system_prompt: str = None, prompt_name: str = "default"):
#         """
#         Start a chat session with history
        
#         Args:
#             system_prompt (str): System prompt to use
#             prompt_name (str): Name of system prompt file
#         """
#         # Load system prompt
#         if system_prompt:
#             prompt_content = system_prompt
#         else:
#             prompt_content = self.load_system_prompt(prompt_name)
        
#         # Initialize chat with system prompt as context
#         self.chat = self.model.start_chat(history=[])
#         self.system_prompt = prompt_content
#         self.prompt_name = prompt_name
        
#         print(f"✓ Chat session started with prompt: {prompt_name}")
#         return self.chat
    
#     def send_chat_message(self, user_input: str, temperature: float = 0.7) -> Dict[str, Any]:
#         """
#         Send a message in an existing chat session
        
#         Args:
#             user_input (str): User's message
#             temperature (float): Controls randomness
        
#         Returns:
#             dict: Response containing text and metadata
#         """
#         if not self.chat:
#             raise ValueError("No active chat session. Call start_chat_session() first.")
        
#         try:
#             # Combine system prompt with user input for context
#             full_message = f"{self.system_prompt}\n\nUser: {user_input}"
            
#             response = self.chat.send_message(
#                 full_message,
#                 generation_config=genai.types.GenerationConfig(
#                     temperature=temperature,
#                 )
#             )
            
#             return {
#                 'success': True,
#                 'text': response.text,
#                 'user_input': user_input,
#                 'error': None
#             }
            
#         except Exception as e:
#             return {
#                 'success': False,
#                 'text': None,
#                 'user_input': user_input,
#                 'error': str(e)
#             }
    
#     def generate_with_context(self, user_input: str, context: str, 
#                              system_prompt: str = None, 
#                              prompt_name: str = "default") -> Dict[str, Any]:
#         """
#         Generate response with additional context
        
#         Args:
#             user_input (str): User's input
#             context (str): Additional context to provide
#             system_prompt (str): System prompt
#             prompt_name (str): Name of system prompt file
#         """
#         try:
#             # Load system prompt
#             if system_prompt:
#                 prompt_content = system_prompt
#             else:
#                 prompt_content = self.load_system_prompt(prompt_name)
            
#             # Combine everything
#             full_prompt = f"{prompt_content}\n\nContext: {context}\n\nUser: {user_input}\n\nAssistant:"
            
#             response = self.model.generate_content(full_prompt)
            
#             return {
#                 'success': True,
#                 'text': response.text,
#                 'prompt_used': prompt_name,
#                 'user_input': user_input,
#                 'error': None
#             }
            
#         except Exception as e:
#             return {
#                 'success': False,
#                 'text': None,
#                 'prompt_used': prompt_name,
#                 'user_input': user_input,
#                 'error': str(e)
#             }


# def extract_sql_from_response(response_text: str) -> str:
#     """
#     Extract SQL query from Gemini response
    
#     Args:
#         response_text (str): Response text from Gemini
    
#     Returns:
#         str: Extracted SQL query
#     """
#     import re
    
#     # Look for SQL code blocks
#     sql_pattern = r"```sql\n(.*?)\n```"
#     matches = re.findall(sql_pattern, response_text, re.DOTALL)
    
#     if matches:
#         return matches[0].strip()
    
#     # If no code blocks, try to find lines starting with SQL keywords
#     sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP']
#     lines = response_text.split('\n')
#     sql_lines = []
    
#     for line in lines:
#         if any(line.strip().upper().startswith(keyword) for keyword in sql_keywords):
#             sql_lines.append(line.strip())
    
#     if sql_lines:
#         return ' '.join(sql_lines)
    
#     return None


# # Convenience functions for easy use

# def get_gemini_response(user_input: str, prompt_name: str = "default", 
#                        api_key: str = None, **kwargs) -> Dict[str, Any]:
#     """
#     Quick function to get Gemini response
    
#     Args:
#         user_input (str): User's input
#         prompt_name (str): Name of system prompt to use
#         api_key (str): Google API key
#         **kwargs: Additional parameters for generate_response
    
#     Returns:
#         dict: Response from Gemini
#     """
#     client = GeminiClient(api_key=api_key)
#     return client.generate_response(user_input, prompt_name=prompt_name, **kwargs)


# def get_sql_from_natural_language(question: str, table_schema: str = None, 
#                                   api_key: str = None) -> Dict[str, Any]:
#     """
#     Convert natural language to SQL query
    
#     Args:
#         question (str): Natural language question about data
#         table_schema (str): Table schema information
#         api_key (str): Google API key
    
#     Returns:
#         dict: Response containing SQL query
#     """
#     client = GeminiClient(api_key=api_key)
    
#     # Use SQL generator prompt
#     response = client.generate_response(
#         user_input=question,
#         prompt_name="sql_generator",
#         temperature=0.3  # Lower temperature for more precise SQL
#     )
    
#     if response['success']:
#         # Extract SQL from response
#         sql_query = extract_sql_from_response(response['text'])
#         response['sql_query'] = sql_query
    
#     return response