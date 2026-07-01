import os
import time
import asyncio
from groq import AsyncGroq, APIStatusError, RateLimitError
from src.core.config.settings import settings
from src.core.logging.logger import logger
from src.core.exceptions.errors import LLMError, MCPToolError

FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "llama-3.1-8b-instant",
]


class LLMService:
    def __init__(self):
        api_key = settings.groq_api_key
        if not api_key:
            api_key = os.getenv("GROQ_API_KEY", "")

        if not api_key:
            logger.error("GROQ_API_KEY not configured in settings or environment")
            raise LLMError("GROQ_API_KEY configuration is missing")

        self.client = AsyncGroq(api_key=api_key)
        self.model = settings.groq_model
        self.max_tokens = settings.groq_max_tokens
        self.temperature = settings.groq_temperature

    async def generate_sql(self, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
        """
        Asynchronously generates SQL query using Groq API, with automatic fallback models.
        Returns a tuple of (sql_query, usage_metrics).
        """
        models_to_try = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]

        for idx, model in enumerate(models_to_try):
            logger.info(f"Sending prompt to Groq using model {model} (attempt {idx + 1}/{len(models_to_try)})...")
            start_time = time.perf_counter()

            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

                latency_ms = (time.perf_counter() - start_time) * 1000.0
                sql = response.choices[0].message.content.strip()

                # Strip markdown formatting
                sql = sql.replace("```sql", "").replace("```", "").strip()

                # Retrieve token usage from response
                usage = getattr(response, "usage", None)
                usage_metrics = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
                    "latency_ms": latency_ms,
                    "model_used": model
                }

                logger.info(
                    f"Groq generation complete using model {model} in {latency_ms:.2f}ms. "
                    f"Tokens - Prompt: {usage_metrics['prompt_tokens']}, "
                    f"Completion: {usage_metrics['completion_tokens']}, "
                    f"Total: {usage_metrics['total_tokens']}"
                )
                return sql, usage_metrics

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                status_code = getattr(e, "status_code", None)

                # Check if it is a transient error (rate limit or service unavailable)
                is_transient = (
                    isinstance(e, (RateLimitError, APIStatusError)) or
                    status_code in (429, 503) or
                    "503" in str(e) or
                    "rate limit" in str(e).lower()
                )

                if is_transient and idx < len(models_to_try) - 1:
                    logger.warning(
                        f"Groq transient error with model {model} (status {status_code}): {e}. "
                        f"Retrying with fallback model in 0.5s..."
                    )
                    await asyncio.sleep(0.5)
                    continue
                else:
                    logger.error(f"Groq API call failed permanently for model {model}: {e}")
                    if idx == len(models_to_try) - 1:
                        raise MCPToolError("LLM unavailable, please retry in a moment") from e
                    else:
                        raise LLMError(f"Groq call failed permanently: {e}") from e
