import re

# Read the analysis service file
with open('/app/intelligence/services/analysis_service.py', 'r') as f:
    content = f.read()

# Add completed_analyses storage after active_analyses initialization
pattern = r'(self\.active_analyses = \{\})'
replacement = r'\1\n        self.completed_analyses = {}  # Store completed analysis results'

if 'self.completed_analyses' not in content:
    content = re.sub(pattern, replacement, content)
    print('✅ Added completed_analyses storage')

# Modify the analysis completion to store results before deletion
pattern = r'(logger\.info\(f"✅ Enhanced analysis \{analysis_id\} completed in \{processing_time:.2f\}s"\)\s+return result)'
replacement = r'# Store completed analysis result\n            self.completed_analyses[analysis_id] = {\n                "status": "completed",\n                "results": result,\n                "completion_time": time.time()\n            }\n            \n            \1'

if 'Store completed analysis result' not in content:
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    print('✅ Added result storage before return')

# Add method to retrieve completed results  
method_pattern = r'(def get_active_analyses\(self\) -> List\[str\]:\s+Get list of active analysis IDs\s+return list\(self\.active_analyses\.keys\(\)\))'
new_method = r'''\1
    
    def get_completed_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        Get completed analysis result
        return self.completed_analyses.get(analysis_id)
    
    def get_all_analyses(self) -> Dict[str, Dict[str, Any]]:
        Get both active and completed analyses
        return {
            "active": dict(self.active_analyses),
            "completed": dict(self.completed_analyses)
        }'''

if 'get_completed_analysis' not in content:
    content = re.sub(method_pattern, new_method, content, flags=re.DOTALL)
    print('✅ Added get_completed_analysis method')

# Write the modified content back
with open('/app/intelligence/services/analysis_service.py', 'w') as f:
    f.write(content)

print('✅ Enhanced analysis service with results storage')
