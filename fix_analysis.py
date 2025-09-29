# Fix to update main.py to return real results

updated_function = """
@app.get("/analyze/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    \"\"\"Get analysis status and results\"\"\"
    
    # Try to get analysis from enhanced service
    if enhanced_service:
        result = enhanced_service.get_analysis_result(analysis_id)
        if result:
            return result
    
    # Fallback to check if it's a recent analysis we know about
    # This would typically check a database or cache
    # For now, return not found if no result exists
    return {
        "analysis_id": analysis_id,
        "status": "not_found",
        "error": "Analysis not found or not yet completed"
    }
"""

# Read the current file
with open("/app/main.py", "r") as f:
    content = f.read()

# Find and replace the function
import re

# Pattern to match the entire function
pattern = r"@app\.get\(\"/analyze/\{analysis_id\}\"\)[\s\S]*?(?=\n(?:@app\.|async def run_analysis))"

# Replace with the updated version
updated_content = re.sub(pattern, updated_function.strip(), content)

# Write back
with open("/app/main.py", "w") as f:
    f.write(updated_content)

print("Fixed get_analysis_status function to return real results")
