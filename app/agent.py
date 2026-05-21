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
# Falls back gracefully if the server is unavailable.
# ---------------------------------------------------------------------------
try:
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
except Exception as e:
    print(f"WARNING: Google Maps MCP unavailable — {e}")
    maps_toolset = None

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
# Agent instruction — adapts based on whether Maps is available
# ---------------------------------------------------------------------------
_maps_step = (
    "Step 5 - Enrich with Google Maps:\n"
    "  For each university city use Google Maps to get:\n"
    "  - Current weather\n"
    "  - 2 nearby places of interest around campus\n"
) if maps_toolset else (
    "Step 5 - (Google Maps unavailable — skip weather step)\n"
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

{_maps_step}
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
  - Weather and nearby places (if available)

Step 7 - Reply to the student:
  Give a clean summary covering universities, scholarships, costs, and visa.
"""

# ---------------------------------------------------------------------------
# Agent — include Maps toolset only if it connected successfully
# ---------------------------------------------------------------------------
_toolsets = [tavily_toolset, scholarship_toolset, filesystem_toolset]
if maps_toolset:
    _toolsets.insert(1, maps_toolset)

agent = LlmAgent(
    name="study_abroad_advisor",
    model="gemini-flash-latest",
    instruction=AGENT_INSTRUCTION,
    tools=_toolsets
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
