"""
Custom MCP Server — Study Abroad Data
Built by students to learn how to create their own MCP server.

This server exposes three tools:
  - get_scholarships(country, course)   — scholarship funding data
  - get_cost_of_living(city)            — monthly living cost breakdown
  - get_visa_requirements(country)      — student visa info

Any MCP client (including ADK agents) can connect to this server
via stdio and call these tools — just like calling Tavily or Google Maps.
"""
import asyncio
import json

import mcp.server.stdio
import mcp.types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions

# ---------------------------------------------------------------------------
# Scholarship Data — extend this dict to add more countries and courses
# ---------------------------------------------------------------------------
SCHOLARSHIPS = {
    "USA": {
        "Machine Learning": [
            {"name": "NSF Graduate Research Fellowship",   "amount": "$37,000/year",              "eligibility": "US citizens and residents"},
            {"name": "Google PhD Fellowship",              "amount": "Full tuition + $40,000 stipend", "eligibility": "PhD students"},
            {"name": "CMU School of CS Fellowship",        "amount": "$30,000/year",              "eligibility": "Admitted CMU students"},
        ],
        "Computer Science": [
            {"name": "NSF Graduate Research Fellowship",   "amount": "$37,000/year",              "eligibility": "US citizens and residents"},
            {"name": "Microsoft Research PhD Fellowship",  "amount": "Full tuition + stipend",    "eligibility": "PhD students"},
        ],
        "Data Science": [
            {"name": "IBM PhD Fellowship",                 "amount": "$35,000/year",              "eligibility": "PhD students"},
            {"name": "Hertz Foundation Fellowship",        "amount": "$38,000/year",              "eligibility": "STEM PhD students"},
        ],
    },
    "Canada": {
        "Machine Learning": [
            {"name": "Vanier Canada Graduate Scholarship", "amount": "$50,000/year",              "eligibility": "Doctoral students"},
            {"name": "NSERC Postgraduate Scholarship",     "amount": "$35,000/year",              "eligibility": "Graduate students"},
        ],
        "Computer Science": [
            {"name": "Vanier Canada Graduate Scholarship", "amount": "$50,000/year",              "eligibility": "Doctoral students"},
            {"name": "Ontario Graduate Scholarship",       "amount": "$15,000/year",              "eligibility": "Ontario university students"},
        ],
    },
    "UK": {
        "Machine Learning": [
            {"name": "EPSRC Doctoral Training Partnership","amount": "Full tuition + 18,000 GBP stipend", "eligibility": "UK/EU residents"},
            {"name": "Chevening Scholarship",              "amount": "Full funding",              "eligibility": "International students"},
        ],
        "Computer Science": [
            {"name": "Commonwealth Scholarship",           "amount": "Full funding",              "eligibility": "Commonwealth citizens"},
            {"name": "EPSRC Doctoral Scholarship",         "amount": "Full tuition + stipend",   "eligibility": "Research students"},
        ],
    },
    "Germany": {
        "Machine Learning": [
            {"name": "DAAD Scholarship",                   "amount": "934 EUR/month + tuition waiver", "eligibility": "International students"},
            {"name": "Deutschlandstipendium",              "amount": "300 EUR/month",             "eligibility": "All students"},
        ],
        "Computer Science": [
            {"name": "DAAD Scholarship",                   "amount": "934 EUR/month + tuition waiver", "eligibility": "International students"},
            {"name": "Heinrich Boll Foundation Scholarship","amount": "850 EUR/month",            "eligibility": "Graduate students"},
        ],
    },
    "Australia": {
        "Machine Learning": [
            {"name": "Australia Awards Scholarship",       "amount": "Full tuition + living expenses", "eligibility": "International students"},
            {"name": "Research Training Program",          "amount": "Full tuition waiver",       "eligibility": "Domestic and international"},
        ],
        "Computer Science": [
            {"name": "Australia Awards Scholarship",       "amount": "Full tuition + living expenses", "eligibility": "International students"},
            {"name": "Endeavour Leadership Program",       "amount": "Up to AUD 272,500",         "eligibility": "High-achieving students"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Cost of Living Data — monthly estimates in USD for popular university cities
# ---------------------------------------------------------------------------
COST_OF_LIVING = {
    "New York": {
        "city": "New York, USA",
        "currency": "USD",
        "monthly_rent_shared": 1200,
        "monthly_rent_studio": 2200,
        "monthly_food": 400,
        "monthly_transport": 130,
        "monthly_utilities": 100,
        "total_estimated_monthly": 1830,
        "notes": "One of the most expensive cities. Consider shared housing near campus."
    },
    "Boston": {
        "city": "Boston, USA",
        "currency": "USD",
        "monthly_rent_shared": 1000,
        "monthly_rent_studio": 1800,
        "monthly_food": 350,
        "monthly_transport": 90,
        "monthly_utilities": 90,
        "total_estimated_monthly": 1530,
        "notes": "Student-friendly area around MIT/Harvard. T-pass discount available."
    },
    "Toronto": {
        "city": "Toronto, Canada",
        "currency": "USD",
        "monthly_rent_shared": 900,
        "monthly_rent_studio": 1500,
        "monthly_food": 300,
        "monthly_transport": 80,
        "monthly_utilities": 80,
        "total_estimated_monthly": 1360,
        "notes": "Large international student community. Transit pass available for students."
    },
    "London": {
        "city": "London, UK",
        "currency": "USD",
        "monthly_rent_shared": 1100,
        "monthly_rent_studio": 1900,
        "monthly_food": 380,
        "monthly_transport": 120,
        "monthly_utilities": 100,
        "total_estimated_monthly": 1700,
        "notes": "18-hour work permit included with student visa. Oyster card for transport."
    },
    "Berlin": {
        "city": "Berlin, Germany",
        "currency": "USD",
        "monthly_rent_shared": 600,
        "monthly_rent_studio": 1000,
        "monthly_food": 250,
        "monthly_transport": 90,
        "monthly_utilities": 70,
        "total_estimated_monthly": 1010,
        "notes": "One of the most affordable major cities in Europe for students."
    },
    "Sydney": {
        "city": "Sydney, Australia",
        "currency": "USD",
        "monthly_rent_shared": 850,
        "monthly_rent_studio": 1500,
        "monthly_food": 350,
        "monthly_transport": 100,
        "monthly_utilities": 90,
        "total_estimated_monthly": 1390,
        "notes": "Part-time work (20 hrs/week) allowed on student visa."
    },
    "Vancouver": {
        "city": "Vancouver, Canada",
        "currency": "USD",
        "monthly_rent_shared": 950,
        "monthly_rent_studio": 1600,
        "monthly_food": 320,
        "monthly_transport": 80,
        "monthly_utilities": 80,
        "total_estimated_monthly": 1430,
        "notes": "High quality of life. Off-campus work permitted up to 20 hrs/week."
    },
}

# ---------------------------------------------------------------------------
# Visa Requirements Data — for international students
# ---------------------------------------------------------------------------
VISA_REQUIREMENTS = {
    "USA": {
        "visa_type": "F-1 Student Visa",
        "processing_time": "3–5 weeks",
        "application_fee": "$510 (SEVIS fee $350 + visa fee $160)",
        "required_documents": [
            "Form I-20 from university",
            "Valid passport (6 months beyond stay)",
            "SEVIS fee payment receipt",
            "DS-160 application form",
            "Bank statement (12 months of funds)",
            "Offer letter / admission letter",
            "Visa interview appointment",
        ],
        "work_permit": "20 hrs/week on campus; CPT/OPT for off-campus",
        "notes": "Schedule visa interview early — appointment slots fill up fast near intake dates."
    },
    "Canada": {
        "visa_type": "Canadian Student Permit",
        "processing_time": "4–8 weeks",
        "application_fee": "CAD 150 (~$110 USD)",
        "required_documents": [
            "Acceptance letter from Designated Learning Institution (DLI)",
            "Valid passport",
            "Proof of funds (CAD 10,000+ per year)",
            "Biometrics (if required)",
            "Statement of purpose",
            "Medical exam (some countries)",
        ],
        "work_permit": "20 hrs/week off campus during studies",
        "notes": "Apply online via IRCC portal. SDS stream available for faster processing."
    },
    "UK": {
        "visa_type": "UK Student Visa (Tier 4)",
        "processing_time": "3–4 weeks",
        "application_fee": "£490 (~$620 USD) + Immigration Health Surcharge",
        "required_documents": [
            "CAS (Confirmation of Acceptance for Studies) from university",
            "Valid passport",
            "Proof of funds (£1,334/month for London, £1,023 elsewhere)",
            "ATAS certificate (for certain courses)",
            "English language test (IELTS/TOEFL)",
            "Tuberculosis test (some countries)",
        ],
        "work_permit": "20 hrs/week during term time; full-time during holidays",
        "notes": "Graduate Route visa allows 2 years post-study work after degree completion."
    },
    "Germany": {
        "visa_type": "German Student Visa (National Visa Type D)",
        "processing_time": "6–12 weeks",
        "application_fee": "€75 (~$82 USD)",
        "required_documents": [
            "University admission letter",
            "Valid passport",
            "Proof of funds (€11,208/year in blocked account)",
            "Health insurance proof",
            "Language certificate (German or English depending on program)",
            "Academic transcripts",
            "Motivational letter",
        ],
        "work_permit": "120 full days or 240 half days per year",
        "notes": "Most programs are tuition-free. Open a blocked account (Sperrkonto) early."
    },
    "Australia": {
        "visa_type": "Student Visa (Subclass 500)",
        "processing_time": "4–6 weeks",
        "application_fee": "AUD 710 (~$470 USD)",
        "required_documents": [
            "CoE (Confirmation of Enrolment) from university",
            "Valid passport",
            "Proof of funds (AUD 24,505/year)",
            "Overseas Student Health Cover (OSHC)",
            "English proficiency (IELTS 6.0+)",
            "Genuine Temporary Entrant (GTE) statement",
        ],
        "work_permit": "48 hrs per fortnight during term; unlimited during holidays",
        "notes": "Post-Study Work visa (Subclass 485) available for 2–4 years after graduation."
    },
}

# ---------------------------------------------------------------------------
# MCP Server Setup
# ---------------------------------------------------------------------------
app = Server("scholarship-mcp-server")


@app.list_tools()
async def list_tools() -> list[mcp_types.Tool]:
    """Advertise available tools to any MCP client that connects."""
    return [
        mcp_types.Tool(
            name="get_scholarships",
            description="Get available scholarships for a specific country and course or field of study",
            inputSchema={
                "type": "object",
                "properties": {
                    "country": {
                        "type": "string",
                        "description": "Country name e.g. USA, Canada, UK, Germany, Australia"
                    },
                    "course": {
                        "type": "string",
                        "description": "Course or field e.g. Machine Learning, Computer Science, Data Science"
                    }
                },
                "required": ["country", "course"]
            }
        ),
        mcp_types.Tool(
            name="get_cost_of_living",
            description="Get estimated monthly cost of living for a university city including rent, food, transport, and utilities",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name e.g. Boston, London, Berlin, Toronto, Sydney"
                    }
                },
                "required": ["city"]
            }
        ),
        mcp_types.Tool(
            name="get_visa_requirements",
            description="Get student visa requirements for a country including visa type, processing time, required documents, and work permit rules",
            inputSchema={
                "type": "object",
                "properties": {
                    "country": {
                        "type": "string",
                        "description": "Country name e.g. USA, Canada, UK, Germany, Australia"
                    }
                },
                "required": ["country"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
    """Execute a tool call requested by an MCP client."""

    # ------------------------------------------------------------------
    # Tool 1: get_scholarships
    # ------------------------------------------------------------------
    if name == "get_scholarships":
        country = arguments.get("country", "").strip()
        course  = arguments.get("course", "").strip()

        country_data = SCHOLARSHIPS.get(country, {})
        if not country_data:
            for key in SCHOLARSHIPS:
                if key.lower() in country.lower() or country.lower() in key.lower():
                    country_data = SCHOLARSHIPS[key]
                    country = key
                    break

        scholarships = country_data.get(course, [])
        if not scholarships:
            for key in country_data:
                if key.lower() in course.lower() or course.lower() in key.lower():
                    scholarships = country_data[key]
                    course = key
                    break

        if scholarships:
            result = {
                "country":      country,
                "course":       course,
                "scholarships": scholarships,
                "total":        len(scholarships)
            }
        else:
            result = {
                "country":      country,
                "course":       course,
                "scholarships": [],
                "message":      f"No scholarships found for {course} in {country}. Check university websites for funding options."
            }
        return [mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

    # ------------------------------------------------------------------
    # Tool 2: get_cost_of_living
    # ------------------------------------------------------------------
    if name == "get_cost_of_living":
        city = arguments.get("city", "").strip()

        city_data = COST_OF_LIVING.get(city, None)
        if not city_data:
            for key in COST_OF_LIVING:
                if key.lower() in city.lower() or city.lower() in key.lower():
                    city_data = COST_OF_LIVING[key]
                    break

        if city_data:
            result = city_data
        else:
            result = {
                "city":    city,
                "message": f"No cost data for '{city}'. Available cities: {', '.join(COST_OF_LIVING.keys())}",
            }
        return [mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

    # ------------------------------------------------------------------
    # Tool 3: get_visa_requirements
    # ------------------------------------------------------------------
    if name == "get_visa_requirements":
        country = arguments.get("country", "").strip()

        visa_data = VISA_REQUIREMENTS.get(country, None)
        if not visa_data:
            for key in VISA_REQUIREMENTS:
                if key.lower() in country.lower() or country.lower() in key.lower():
                    visa_data = VISA_REQUIREMENTS[key]
                    country = key
                    break

        if visa_data:
            result = {"country": country, **visa_data}
        else:
            result = {
                "country": country,
                "message": f"No visa data for '{country}'. Available countries: {', '.join(VISA_REQUIREMENTS.keys())}",
            }
        return [mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

    # ------------------------------------------------------------------
    # Unknown tool
    # ------------------------------------------------------------------
    return [mcp_types.TextContent(
        type="text",
        text=json.dumps({"error": f"Tool '{name}' not found on this server"})
    )]


# ---------------------------------------------------------------------------
# Server Entry Point — runs as a stdio process
# ---------------------------------------------------------------------------
async def run():
    async with mcp.server.stdio.stdio_server() as (read, write):
        await app.run(
            read,
            write,
            InitializationOptions(
                server_name=app.name,
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(run())
