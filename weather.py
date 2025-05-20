from typing import Any
import httpx
import shutil
import sys
import subprocess
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Check for UV dependency first
def check_uv_dependency():
    uv_path = shutil.which('uv')
    if uv_path is None:
        print("Error: 'uv' executable not found in PATH", file=sys.stderr)
        print("Please install UV using: pip install uv", file=sys.stderr)
        return False
    
    try:
        # Just verify UV works
        process = subprocess.Popen(
            [uv_path, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"UV process error: {stderr}", file=sys.stderr)
            return False
        
        print(f"Using UV at: {uv_path}", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"Error running UV: {str(e)}", file=sys.stderr)
        return False

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API request error: {str(e)}", file=sys.stderr)
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.
    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)
    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."
    if not data["features"]:
        return "No active alerts for this state."
    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.
    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)
    if not points_data:
        return "Unable to fetch forecast data for this location."
    
    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)
    if not forecast_data:
        return "Unable to fetch detailed forecast."
    
    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)
    return "\n---\n".join(forecasts)

if __name__ == "__main__":
    # Check UV dependency before starting server
    print("Initializing weather server...", file=sys.stderr)
    if not check_uv_dependency():
        sys.exit(1)
        
    # Initialize and run the server
    print("Starting MCP server...", file=sys.stderr)
    mcp.run(transport='stdio')