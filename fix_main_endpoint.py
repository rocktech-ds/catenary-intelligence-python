import re

# Read the main.py file
with open('/app/main.py', 'r') as f:
    content = f.read()

# Find and replace the placeholder get_analysis_status function
old_function_pattern = r'@app\.get\("/analyze/\{analysis_id\}"\)\s*async def get_analysis_status\(analysis_id: str\):\s*"""Get analysis status and results"""\s*# In a production system, this would check a database or cache\s*# For now, return a placeholder response\s*return \{\s*"analysis_id": analysis_id,\s*"status": "completed",\s*"results": \{\s*"message": "Analysis functionality ready - integration with main API pending"\s*\}\s*\}'

new_function = '''@app.get("/analyze/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """Get analysis status and results"""
    if not enhanced_service:
        raise HTTPException(
            status_code=503,
            detail="Enhanced analysis service is not available"
        )

    try:
        # First check if it's an active analysis
        active_status = await enhanced_service.get_analysis_status(analysis_id)
        if active_status:
            return {
                "analysis_id": analysis_id,
                "status": active_status.get("status", "unknown"),
                "progress": active_status.get("progress"),
                "current_step": active_status.get("current_step"),
                "results": None  # Not completed yet
            }

        # Check if it's a completed analysis
        completed_analysis = enhanced_service.get_completed_analysis(analysis_id)
        if completed_analysis:
            return {
                "analysis_id": analysis_id,
                "status": completed_analysis.get("status", "completed"),
                "results": completed_analysis.get("results")
            }

        # Analysis not found
        raise HTTPException(
            status_code=404,
            detail=f"Analysis {analysis_id} not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analysis status: {str(e)}"
        )'''

# Use a more specific replacement approach
# Find the specific function block
start_marker = '@app.get("/analyze/{analysis_id}")'
end_marker = 'async def run_analysis('

start_pos = content.find(start_marker)
if start_pos != -1:
    # Find the end of this function (start of next function)
    end_pos = content.find(end_marker, start_pos)
    if end_pos != -1:
        # Replace the function
        before = content[:start_pos]
        after = content[end_pos:]
        content = before + new_function + '\n\n' + after
        print('✅ Replaced get_analysis_status function')
    else:
        print('❌ Could not find end of function')
else:
    print('❌ Could not find get_analysis_status function')

# Write the modified content back
with open('/app/main.py', 'w') as f:
    f.write(content)

print('✅ Fixed main.py get_analysis_status endpoint to use enhanced service')