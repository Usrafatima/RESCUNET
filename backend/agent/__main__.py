"""
RescuNet Agent CLI Demo.

Run with: python -m agent

This script demonstrates the Strands agent analyzing an incident
and producing a response recommendation.

Usage:
    python -m agent                    # Analyze RSN-000001 (default)
    python -m agent RSN-000002         # Analyze a specific incident
"""

import sys
import os

# Add the backend directory to Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.rescuenet_agent import create_agent
from agent.prompts import SYSTEM_PROMPT


def main():
    """Run the agent CLI demo."""
    # Determine incident ID from args
    incident_id = sys.argv[1] if len(sys.argv) > 1 else "RSN-000001"

    print("=" * 60)
    print("RESCUNET AI RESPONSE")
    print("=" * 60)
    print()
    print(f"Analyzing Incident: {incident_id}")
    print()
    print("Invoking Strands Agent with tools...")
    print("-" * 60)

    # Create agent with console output
    agent = create_agent()

    prompt = f"""Analyze incident {incident_id} and provide a response recommendation.

Follow your workflow:
1. Retrieve the incident details
2. Classify the emergency type and priority
3. Find available resources that match the incident type
4. Check resource availability and calculate distances
5. Recommend the best resource with reasoning

Remember: Human approval is REQUIRED before any dispatch."""

    try:
        result = agent(prompt)
        print()
        print("=" * 60)
        print("HUMAN APPROVAL: REQUIRED")
        print("=" * 60)
    except Exception as e:
        print()
        print(f"Error: {e}")
        print()
        print("Make sure GOOGLE_API_KEY is set in backend/.env")
        print("You can get an API key from https://aistudio.google.com/apikey")
        sys.exit(1)


if __name__ == "__main__":
    main()
