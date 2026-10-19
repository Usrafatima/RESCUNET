"""
RescuNet Strands Agent.

Creates and configures the Strands Agent with:
- Google Gemini as model provider (configurable)
- All 5 incident/resource tools
- System prompt defining agent behavior
- structured_output_model for reliable structured extraction
"""

import logging
import time
from typing import Optional

from strands import Agent
from strands.models.gemini import GeminiModel

from agent.config import config
from agent.models import AgentRecommendation, PriorityAnalysisResult
from agent.prompts import SYSTEM_PROMPT
from agent.tools.incident_tools import (
    calculate_distance,
    find_available_resources,
    get_incident,
    get_resource_status,
    list_active_incidents,
)

logger = logging.getLogger(__name__)

# All tools available to the agent
AGENT_TOOLS = [
    get_incident,
    list_active_incidents,
    find_available_resources,
    get_resource_status,
    calculate_distance,
]


class ModelUnavailableException(Exception):
    """Raised when the AI model is temporarily unavailable (503 UNAVAILABLE / high demand)."""

    def __init__(self, message: str = "This model is currently experiencing high demand. Please try again later."):
        super().__init__(message)
        self.message = message


class ModelRateLimitedException(Exception):
    """Raised when the AI model quota or rate limit is reached (429 RESOURCE_EXHAUSTED)."""

    def __init__(self, message: str = "AI service rate limit or quota reached. Please try again later."):
        super().__init__(message)
        self.message = message


def _is_transient_error(error: Exception) -> tuple[bool, str, int]:
    """Classify whether an exception is a transient 503 or 429 error.

    Returns:
        (is_retryable, error_message, status_code)
    """
    err_str = str(error).lower()

    if "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
        return (
            True,
            "The Gemini model is currently experiencing high demand. Please try again shortly.",
            503,
        )

    if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str or "rate limit" in err_str:
        # If it's a daily project quota exhaustion (hours to wait), do not retry immediately
        if "day" in err_str or "daily" in err_str or ("retry in " in err_str and ("h" in err_str or "m" in err_str)):
            return (
                False,
                "Gemini API request quota exceeded for the current project. Please check quota limits.",
                429,
            )
        return (
            True,
            "Gemini API rate limit reached. Please wait a moment and try again.",
            429,
        )

    return (False, str(error), 500)


def _run_agent_with_retry(agent, prompt: str, output_model, incident_id: str, max_retries: int = 2):
    """Execute the agent with bounded retry and exponential backoff for transient errors."""
    delay = 1.0
    last_error = None
    is_retryable = False
    error_msg = ""
    status_code = 500

    for attempt in range(max_retries + 1):
        try:
            return agent(prompt, structured_output_model=output_model)
        except Exception as e:
            last_error = e
            is_retryable, error_msg, status_code = _is_transient_error(e)
            logger.warning(
                f"Agent run attempt {attempt + 1}/{max_retries + 1} for {incident_id} failed: {e}"
            )
            if is_retryable and attempt < max_retries:
                time.sleep(delay)
                delay *= 2.0  # Exponential backoff: 1.0s, 2.0s
            else:
                break

    if last_error is not None:
        if status_code == 503:
            raise ModelUnavailableException(error_msg) from last_error
        elif status_code == 429:
            raise ModelRateLimitedException(error_msg) from last_error
        raise last_error


def create_agent(callback_handler=None) -> Agent:
    """Create and return a configured RescuNet agent.

    Args:
        callback_handler: Optional callback handler for streaming.
                         Pass None to suppress console output.

    Returns:
        Configured Strands Agent instance
    """
    if not config.has_api_key:
        logger.warning(
            "No GOOGLE_API_KEY configured. Agent will not be able to make LLM calls. "
            "Set GOOGLE_API_KEY in backend/.env"
        )

    model = GeminiModel(
        client_args={
            "api_key": config.google_api_key,
        },
        model_id=config.gemini_model_id,
        params={
            "temperature": config.gemini_temperature,
            "max_output_tokens": config.gemini_max_output_tokens,
        },
    )

    agent = Agent(
        model=model,
        tools=AGENT_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=callback_handler,
    )

    return agent


def analyze_incident(incident_id: str) -> Optional[dict]:
    """Analyze a specific incident using the RescuNet agent.

    This is the main entry point for incident analysis. It performs a two-step
    process using Strands' structured_output_model:

    Step 1: Tool-using analysis
        The agent calls get_incident(), find_available_resources(),
        get_resource_status(), and calculate_distance() to gather data.

    Step 2: Structured output
        Strands adds a StructuredOutputTool that the agent calls as its
        final action. The tool validates the output against AgentRecommendation
        and stores it in result.structured_output. No text parsing needed.

    Args:
        incident_id: The incident to analyze (e.g., RSN-000001)

    Returns:
        Dict with the agent's recommendation, or None on failure
    """
    agent = create_agent(callback_handler=None)

    prompt = f"""Analyze incident {incident_id} and provide a response recommendation.

Follow your workflow:
1. Retrieve the incident details using get_incident("{incident_id}")
2. Classify the emergency type and priority
3. Find available resources that match the incident type
4. Check resource availability and calculate distances
5. Recommend the best resource with reasoning

Remember: Human approval is REQUIRED before any dispatch.
Do NOT claim anything was dispatched.

When you are done with your analysis, you MUST call the StructuredOutputTool
with all required fields. Use the exact values returned by the tools -- do
not invent or round them."""

    try:
        # Use structured_output_model with bounded retry for transient errors
        result = _run_agent_with_retry(
            agent, prompt, AgentRecommendation, incident_id=incident_id
        )

        # Strands stores the validated Pydantic model in result.structured_output
        if result.structured_output is not None:
            recommendation = result.structured_output
            logger.info(
                f"Structured recommendation received for {incident_id}: "
                f"{recommendation.recommended_action.resource_id} "
                f"({recommendation.recommended_action.resource_name})"
            )
            return {
                "incident_id": incident_id,
                "analysis": recommendation.analysis,
                "status": "recommendation_ready",
                "human_approval_required": True,
                "recommendation": recommendation.model_dump(),
            }

        # Fallback: extract text if structured output wasn't produced
        analysis_text = ""
        if hasattr(result, "message"):
            message = result.message
            if isinstance(message, dict) and "content" in message:
                for block in message["content"]:
                    if isinstance(block, dict) and "text" in block:
                        analysis_text = block["text"]
                        break
            if not analysis_text:
                analysis_text = str(message)
        else:
            analysis_text = str(result)

        if not analysis_text:
            logger.error(f"Agent produced empty response for {incident_id}")
            return None

        logger.warning(
            f"Structured output not available for {incident_id}. "
            f"Returning raw analysis text."
        )
        return {
            "incident_id": incident_id,
            "analysis": analysis_text,
            "status": "recommendation_ready",
            "human_approval_required": True,
            "recommendation": None,
        }

    except (ModelUnavailableException, ModelRateLimitedException):
        raise
    except Exception as e:
        logger.error(f"Agent analysis failed for {incident_id}: {e}")
        return None


def analyze_priority(incident_id: str) -> Optional[dict]:
    """Analyze an incident's priority factors using the RescuNet agent.

    This uses a focused prompt to extract structured priority factors.
    The LLM provides the factor values; the final score is calculated
    deterministically by the priority service.

    Args:
        incident_id: The incident to analyze (e.g., RSN-000001)

    Returns:
        Dict with priority factors, or None on failure
    """
    agent = create_agent(callback_handler=None)

    prompt = f"""Analyze the priority of incident {incident_id}.

Use get_incident("{incident_id}") to retrieve the incident details.
Then assess these priority factors:

1. SEVERITY (0-100): How severe is this emergency?
   - 90-100: Immediate threat to life (trapped, critical injury, active fire)
   - 70-89: Serious but not immediately life-threatening
   - 40-69: Moderate urgency
   - 0-39: Low urgency

2. PEOPLE AFFECTED (0-100): Scale the impact by number of people.
   - 90-100: 10+ people affected
   - 70-89: 5-9 people
   - 40-69: 2-4 people
   - 0-39: 1 person

3. URGENCY (0-100): How time-sensitive is the response?
   - 90-100: Minutes matter (collapse, severe bleeding, fire spreading)
   - 70-89: Hours matter (medical need, structural damage)
   - 40-69: Same-day response needed
   - 0-39: Can wait for scheduled response

4. RESOURCE NEED (0-100): How specialized is the required response?
   - 90-100: Highly specialized (heavy rescue, surgical)
   - 70-89: Specialized team (fire, medical)
   - 40-69: General response capability
   - 0-39: Basic supplies or shelter

Also identify:
- recommended_resource_type: What type of resource is needed?
- reason: A concise explanation of why this priority assessment

When done, call the StructuredOutputTool with all required fields."""

    try:
        result = _run_agent_with_retry(
            agent, prompt, PriorityAnalysisResult, incident_id=incident_id
        )

        if result.structured_output is not None:
            analysis = result.structured_output
            logger.info(
                f"Priority analysis for {incident_id}: "
                f"{analysis.priority_label.value}"
            )
            return {
                "incident_id": incident_id,
                "priority_label": analysis.priority_label.value,
                "factors": analysis.factors.model_dump(),
                "recommended_resource_type": analysis.recommended_resource_type,
            }

        logger.warning(
            f"Priority structured output not available for {incident_id}"
        )
        return None

    except (ModelUnavailableException, ModelRateLimitedException):
        raise
    except Exception as e:
        logger.error(f"Priority analysis failed for {incident_id}: {e}")
        return None
