import os
import asyncio
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from mcp import StdioServerParameters
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

TAVILY_API_KEY      = os.getenv("TAVILY_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

REPORTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "reports")
)
os.makedirs(REPORTS_DIR, exist_ok=True)

SCHOLARSHIP_SERVER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scholarship_mcp_server", "scholarship_server.py")
)

AGENT_INSTRUCTION = f"""
You are a Study Abroad Advisor helping students find the best universities.

When a student asks about studying abroad for a course or field:

Step 1 - Search with Tavily:
  Search for top 3 universities for that course.
  Collect: name, country, city, ranking, why it is good.

Step 2 - Get Scholarships:
  For each university's country and course use get_scholarships tool
  to find available scholarships.

Step 3 - Get Cost of Living:
  For each university city use get_cost_of_living tool
  to get monthly rent, food, transport, and total estimated cost.

Step 4 - Get Visa Requirements:
  For each university's country use get_visa_requirements tool
  to get visa type, processing time, and required documents.

Step 5 - Enrich with Google Maps:
  For each university city use Google Maps to get:
  - Current weather
  - 2 nearby places of interest around campus

Step 6 - Save Report with Filesystem:
  Save a markdown report to: {REPORTS_DIR}
  Filename: <course>_universities_report.md
  Structure:
  # Study Abroad Report: [Course]
  ## [University Name]
  - Location, Ranking, Why recommended
  - Scholarships available
  - Monthly cost of living breakdown
  - Visa type and key requirements
  - Weather and nearby places

Step 7 - Reply to the student:
  Give a clean summary covering universities, scholarships, costs, visa, and weather.
"""

# ---------------------------------------------------------------------------
# MCP Server 1 — Tavily Remote MCP (web search)
# ---------------------------------------------------------------------------
tavily_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
    )
)

# ---------------------------------------------------------------------------
# MCP Server 2 — Google Maps Remote MCP (weather + places + routes)
# ---------------------------------------------------------------------------
maps_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://mapstools.googleapis.com/mcp",
        headers={
            "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
    )
)

# ---------------------------------------------------------------------------
# MCP Server 3 — Custom Scholarship MCP (our own server)
# ---------------------------------------------------------------------------
scholarship_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="python",
            args=[SCHOLARSHIP_SERVER]
        ),
        timeout=30
    )
)

# ---------------------------------------------------------------------------
# MCP Server 4 — Filesystem Local MCP (save reports)
# ---------------------------------------------------------------------------
filesystem_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", REPORTS_DIR]
        ),
        timeout=30
    )
)

# ---------------------------------------------------------------------------
# Agent — defined synchronously with all 4 MCP toolsets
# ---------------------------------------------------------------------------
agent = LlmAgent(
    name="study_abroad_advisor",
    model="gemini-flash-latest",
    instruction=AGENT_INSTRUCTION,
    tools=[tavily_toolset, maps_toolset, scholarship_toolset, filesystem_toolset]
)


async def run_query(question):
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="study_abroad_finder",
        user_id="student",
        session_id="session_1"
    )

    runner = Runner(
        agent=agent,
        app_name="study_abroad_finder",
        session_service=session_service
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=question)]
    )

    final_response = ""
    async for event in runner.run_async(
        user_id="student",
        session_id="session_1",
        new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    return final_response


def ask(question):
    return asyncio.run(run_query(question))
