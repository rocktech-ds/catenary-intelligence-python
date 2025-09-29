"""
Pandas Analyzer - Data processing and table analysis
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class PandasAnalyzer:
    def get_status(self):
        return {
            'available': True,
            'version': pd.__version__,
            'description': 'Data processing and table analysis'
        }
    
    def _serialize_numpy_values(self, obj):
        """Convert numpy types to native Python types for JSON serialization"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._serialize_numpy_values(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_numpy_values(item) for item in obj]
        elif pd.isna(obj):
            return None
        else:
            return obj
    
    async def analyze_tables(self, tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze tables with Pandas"""
        try:
            result = {
                'success': True,
                'processed_tables': [],
                'statistics': [],
                'data_quality': {}
            }
            
            total_rows = 0
            total_duplicates = 0
            total_missing = 0
            
            for i, table_data in enumerate(tables):
                if not table_data.get('data'):
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(table_data['data'][1:], columns=table_data['data'][0] if table_data['data'] else [])
                
                # Basic statistics
                stats = {
                    'table_id': f"table_{i+1}",
                    'row_count': len(df),
                    'column_count': len(df.columns),
                    'data_types': df.dtypes.astype(str).to_dict(),
                    'missing_data_percentage': (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100 if not df.empty else 0
                }
                
                # Convert DataFrame to records and serialize numpy types
                df_records = df.to_dict('records')
                serialized_records = [self._serialize_numpy_values(record) for record in df_records]
                
                # Process table for BOM detection
                processed_table = {
                    'table_id': f"table_{i+1}",
                    'source_page': table_data.get('page', 1),
                    'headers': [str(col) for col in df.columns.tolist()],
                    'rows': serialized_records,
                    'table_type': self.detect_table_type(df),
                    'statistics': self._serialize_numpy_values(stats)
                }
                
                result['processed_tables'].append(processed_table)
                result['statistics'].append(self._serialize_numpy_values(stats))
                
                # Aggregate quality metrics
                total_rows += len(df)
                total_duplicates += int(df.duplicated().sum())
                total_missing += int(df.isnull().sum().sum())
            
            # Overall data quality report
            result['data_quality'] = {
                'total_rows': int(total_rows),
                'duplicate_rows': int(total_duplicates),
                'missing_values': int(total_missing),
                'data_types': {}
            }
            
            logger.info(f"✅ Pandas: Processed {len(result['processed_tables'])} tables with {total_rows} total rows")
            return result
            
        except Exception as e:
            logger.error(f"❌ Pandas analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def detect_table_type(self, df: pd.DataFrame) -> str:
        """Detect if table is a BOM, specifications, or other"""
        if df.empty:
            return 'unknown'
        
        headers_lower = [str(col).lower() for col in df.columns]
        
        # BOM indicators
        bom_keywords = ['part', 'item', 'qty', 'quantity', 'description', 'material', 'component']
        bom_score = sum(1 for keyword in bom_keywords if any(keyword in header for header in headers_lower))
        
        # Specification indicators  
        spec_keywords = ['specification', 'parameter', 'value', 'requirement', 'standard']
        spec_score = sum(1 for keyword in spec_keywords if any(keyword in header for header in headers_lower))
        
        if bom_score >= 2:
            return 'bom'
        elif spec_score >= 2:
            return 'specifications'
        elif len(df.columns) >= 3 and len(df) >= 3:
            return 'data'
        else:
            return 'unknown'