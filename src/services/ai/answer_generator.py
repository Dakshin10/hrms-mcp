import os
import json
import time
from groq import AsyncGroq
from src.core.config.settings import settings
from src.core.logging.logger import logger


class AnswerGenerator:
    def __init__(self):
        api_key = settings.groq_api_key
        if not api_key:
            api_key = os.getenv("GROQ_API_KEY", "")
        self.client = AsyncGroq(api_key=api_key) if api_key else None

    async def generate_answer(
        self,
        question: str,
        sql: str,
        results: list[dict],
        model: str = "openai/gpt-oss-120b"
    ) -> str:
        """
        Converts SQL query results into a human-readable business sentence or paragraph.
        """
        if not results or all(
            v is None 
            for row in results 
            for v in row.values()
        ):
            logger.info("Answer generator mode: direct_format (empty results or all values None)")
            return "No data found for your query."

        # Check for CANNOT_ANSWER security response
        if results and len(results) == 1:
            first_row = results[0]
            if "error" in first_row and str(first_row.get("error")).upper() == "CANNOT_ANSWER":
                reason = first_row.get("reason", "Forbidden action")
                if isinstance(reason, str) and "reason:" in reason.lower():
                    reason = reason.split(":", 1)[1].strip()
                logger.info(f"Answer generator mode: security_blocked ({reason})")
                return f"Validation failed: Forbidden action. Reason: {reason}"

        # If all metric columns in a single-row result are None, treat it as empty results
        if results and len(results) == 1:
            metric_keys = [k for k in results[0].keys() if any(term in k.lower() for term in ["count", "total", "avg", "sum", "achievement", "adherence", "rate", "utilization", "rework", "percentage"])]
            if metric_keys and all(results[0][k] is None or str(results[0][k]).lower() in ("none", "null") for k in metric_keys):
                logger.info("Answer generator mode: direct_count (empty results due to null metrics)")
                return "No data found for your query."

        # Check for aggregate / count result in a single row
        if len(results) == 1:
            keys = list(results[0].keys())
            
            # Check for multi-column aggregate results (like ftr_rate + rework_rate in the same row)
            ftr_key = next((k for k in keys if "ftr" in k.lower()), None)
            rework_key = next((k for k in keys if "rework" in k.lower()), None)
            if ftr_key and rework_key:
                ftr_val = results[0][ftr_key]
                rework_val = results[0][rework_key]
                if (ftr_val is not None and str(ftr_val) != "None" and 
                    rework_val is not None and str(rework_val) != "None"):
                    logger.info("Answer generator mode: direct_multi_aggregate (ftr and rework)")
                    return f"Current metrics — FTR rate: {ftr_val}%, Rework rate: {rework_val}%"
                else:
                    logger.info("Direct ftr/rework metrics contain None or empty. Falling through to LLM.")
                    pass
            elif keys:
                first_key = keys[0]
                is_aggregate = any(
                    agg in first_key.lower()
                    for agg in ["count", "total", "avg", "sum", "achievement", "adherence", "rate", "utilization", "rework"]
                )

                if is_aggregate:
                    value = results[0][first_key]
                    if value is None or str(value) == "None":
                        return "No data found for your query."

                    inferred_entity = "items"
                    q_lower = question.lower()
                    if "employee" in q_lower or "staff" in q_lower or "person" in q_lower or "people" in q_lower:
                        inferred_entity = "employees"
                    elif "department" in q_lower:
                        inferred_entity = "departments"
                    elif "rework" in q_lower:
                        inferred_entity = "reworks"
                    elif "task" in q_lower or "work" in q_lower:
                        inferred_entity = "tasks"
                    elif "hour" in q_lower:
                        inferred_entity = "hours"

                    logger.info("Answer generator mode: direct_count")
                    return f"There are currently {value} {inferred_entity} in the system."

        # Multi-row patterns
        if len(results) >= 2:
            keys = list(results[0].keys())
            
            # PATTERN A — Ranked list (results have a score/percentage column)
            metric_col = None
            for k in keys:
                if any(term in k.lower() for term in ["rate", "percentage", "score", "adherence", "utilization"]):
                    metric_col = k
                    break
            
            if metric_col:
                entity_col = None
                for k in keys:
                    if k != metric_col and any(term in k.lower() for term in ["name", "id", "dept", "department"]):
                        entity_col = k
                        break
                if not entity_col and len(keys) > 1:
                    for k in keys:
                        if k != metric_col:
                            entity_col = k
                            break
                if entity_col:
                    lines = [f"Here are the results ranked by {metric_col}:"]
                    for idx, r in enumerate(results[:10], 1):
                        name_val = r.get(entity_col, "")
                        metric_val = r.get(metric_col, "")
                        suffix = "%" if not str(metric_val).endswith("%") else ""
                        lines.append(f"{idx}. {name_val} — {metric_val}{suffix}")
                    logger.info("Answer generator mode: ranked_list_format")
                    return "\n".join(lines)

            # PATTERN B — Flagged employees (results have employee_id AND any of: reason, flag, status, attention)
            has_emp_id = "employee_id" in keys
            flag_col = None
            for k in keys:
                if any(term in k.lower() for term in ["reason", "flag", "status", "attention"]):
                    flag_col = k
                    break
            if has_emp_id and flag_col:
                lines = [f"{len(results)} employees flagged:"]
                for r in results[:10]:
                    emp_id = r.get("employee_id", "")
                    emp_name = r.get("employee_name", emp_id)
                    dept = r.get("department", "N/A")
                    reason = r.get(flag_col, "")
                    lines.append(f"- {emp_name} ({dept}): {reason}")
                logger.info("Answer generator mode: flagged_format")
                return "\n".join(lines)

            # PATTERN C — Department comparison (results have department column)
            dept_col = None
            for k in keys:
                if k.lower() in ["department", "dept"]:
                    dept_col = k
                    break
            if dept_col:
                other_col = None
                for k in keys:
                    if k != dept_col:
                        other_col = k
                        break
                if other_col:
                    lines = ["Department breakdown:"]
                    for r in results[:10]:
                        dept = r.get(dept_col, "")
                        val = r.get(other_col, "")
                        lines.append(f"- {dept}: {val}")
                    logger.info("Answer generator mode: dept_format")
                    return "\n".join(lines)

        # If LLM key is missing, go straight to fallback table
        if not self.client:
            logger.warning("GROQ_API_KEY missing for AnswerGenerator, using fallback table")
            return self._format_as_table(results)

        # Generate NL answer via LLM
        system_prompt = (
            "You are an HR data analyst. Convert SQL query results into "
            "one clear, concise business sentence or short paragraph. "
            "Never mention SQL. Use professional HR language. "
            "Be specific with numbers."
        )
        user_prompt = f"Question: {question}\nResults (JSON): {json.dumps(results[:10])}\nWrite a natural language answer."

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=300
            )
            answer = response.choices[0].message.content.strip()
            logger.info("Answer generator mode: llm_generated")
            return self._normalize_empty_answer(answer)
        except Exception as e:
            logger.error(f"Answer generator LLM call failed: {e}. Falling back to text table.")
            logger.info("Answer generator mode: fallback_table")
            return self._format_as_table(results)

    def _normalize_empty_answer(self, answer: str) -> str:
        EMPTY_SIGNALS = [
            "unavailable", "no data available", "not available",
            "no records", "no results", "currently no", 
            "does not exist", "cannot be found", "not found",
            "no information"
        ]
        answer_lower = answer.lower()
        if any(signal in answer_lower for signal in EMPTY_SIGNALS):
            return "No data found for your query."
        return answer

    def _format_as_table(self, results: list[dict]) -> str:
        """
        Formats a list of dicts as a clean plain text table.
        """
        if not results:
            return "No data found."
        keys = list(results[0].keys())
        widths = {k: len(k) for k in keys}
        for r in results:
            for k in keys:
                widths[k] = max(widths[k], len(str(r.get(k, ""))))

        header = " | ".join(k.ljust(widths[k]) for k in keys)
        separator = "-+-".join("-" * widths[k] for k in keys)
        rows = []
        for r in results:
            row = " | ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys)
            rows.append(row)

        return f"{header}\n{separator}\n" + "\n".join(rows)


# Module-level singleton
answer_generator = AnswerGenerator()


async def generate_answer(
    question: str,
    sql: str,
    results: list[dict],
    model: str = "openai/gpt-oss-120b"
) -> str:
    """
    Shortcut function wrapper for module-level answer_generator singleton.
    """
    return await answer_generator.generate_answer(question, sql, results, model)
