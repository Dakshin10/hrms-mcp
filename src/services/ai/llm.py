import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

SYSTEM_PROMPT = """
You are an expert SQL generator for a SQLite database.

Rules:
1. Return ONLY valid SQL.
2. Do NOT wrap SQL in markdown.
3. Do NOT explain the query.
4. Generate SQLite-compatible SQL only.
5. ONLY generate SELECT statements.
6. NEVER generate:
   - INSERT
   - UPDATE
   - DELETE
   - DROP
   - ALTER
   - TRUNCATE
   - CREATE
7. Always use meaningful aliases for aggregates.
   Example:
   SELECT COUNT(*) AS employee_count
8. Use only tables and columns provided in the schema.
9. If the question cannot be answered from the schema, return:
   SELECT 'INSUFFICIENT_SCHEMA' AS error;
"""


def generate_sql(prompt: str) -> str:
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=300
    )

    sql = response.choices[0].message.content.strip()

    # Remove accidental markdown if model returns it
    sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql