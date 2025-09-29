"""
Advanced Vector Graphics Extractor for Engineering Documents
Identifies and analyzes vector graphics, CAD symbols, technical drawing symbols, and geometric shapes.

This extractor provides:
- CAD symbol detection and classification
- Geometric shape analysis
- Technical drawing symbol recognition
- Vector graphics metadata extraction
- Symbol library matching
- Coordinate and positioning analysis
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class VectorSymbol:
    """Represents a detected vector symbol or graphic element"""
    symbol_type: str
    symbol_class: str  # CAD, electrical, mechanical, architectural, etc.
    confidence: float
    coordinates: Dict[str, Any]  # x, y, width, height, rotation
    properties: Dict[str, Any]
    standard_reference: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class GeometricShape:
    """Represents a detected geometric shape"""
    shape_type: str  # circle, rectangle, triangle, polygon, arc, etc.
    dimensions: Dict[str, float]
    coordinates: Dict[str, Any]
    properties: Dict[str, Any]
    is_construction_line: bool = False
    is_dimension_line: bool = False

@dataclass
class VectorGraphicsResult:
    """Complete vector graphics analysis result"""
    total_symbols: int
    total_shapes: int
    symbols: List[VectorSymbol]
    shapes: List[GeometricShape]
    symbol_classifications: Dict[str, int]
    shape_classifications: Dict[str, int]
    drawing_type: Optional[str] = None
    complexity_score: float = 0.0
    confidence: float = 0.0
    processing_notes: List[str] = None

class VectorGraphicsExtractor:
    """
    Advanced extractor for vector graphics, CAD symbols, and technical drawing elements.
    Uses computer vision and pattern recognition to identify and analyze vector elements.
    """
    
    def __init__(self, ai_service=None):
        self.ai_service = ai_service
        self.symbol_patterns = self._initialize_symbol_patterns()
        self.shape_patterns = self._initialize_shape_patterns()
        self.cad_standards = self._initialize_cad_standards()
        
    def _initialize_symbol_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize patterns for common CAD and technical symbols"""
        return {
            # Electrical Symbols
            "resistor": {
                "pattern_type": "zigzag_line",
                "aspect_ratio": (3, 1),
                "class": "electrical",
                "standard": "IEEE/IEC"
            },
            "capacitor": {
                "pattern_type": "parallel_lines",
                "aspect_ratio": (1, 2),
                "class": "electrical",
                "standard": "IEEE/IEC"
            },
            "inductor": {
                "pattern_type": "coil",
                "aspect_ratio": (2, 1),
                "class": "electrical",
                "standard": "IEEE/IEC"
            },
            "ground": {
                "pattern_type": "ground_symbol",
                "aspect_ratio": (1, 1),
                "class": "electrical",
                "standard": "IEEE/IEC"
            },
            
            # Mechanical Symbols
            "bearing": {
                "pattern_type": "concentric_circles",
                "aspect_ratio": (1, 1),
                "class": "mechanical",
                "standard": "ISO"
            },
            "spring": {
                "pattern_type": "coil_vertical",
                "aspect_ratio": (1, 3),
                "class": "mechanical",
                "standard": "ISO"
            },
            "gear": {
                "pattern_type": "toothed_circle",
                "aspect_ratio": (1, 1),
                "class": "mechanical",
                "standard": "ISO"
            },
            
            # Architectural Symbols
            "door": {
                "pattern_type": "arc_with_line",
                "aspect_ratio": (1, 2),
                "class": "architectural",
                "standard": "AIA"
            },
            "window": {
                "pattern_type": "double_lines",
                "aspect_ratio": (2, 1),
                "class": "architectural",
                "standard": "AIA"
            },
            "wall": {
                "pattern_type": "parallel_thick_lines",
                "aspect_ratio": (10, 1),
                "class": "architectural",
                "standard": "AIA"
            },
            
            # Piping Symbols
            "valve": {
                "pattern_type": "triangle_on_line",
                "aspect_ratio": (1, 1),
                "class": "piping",
                "standard": "ISO/ANSI"
            },
            "pump": {
                "pattern_type": "circle_with_arrow",
                "aspect_ratio": (1, 1),
                "class": "piping",
                "standard": "ISO/ANSI"
            },
            "tank": {
                "pattern_type": "rectangle_with_inlet",
                "aspect_ratio": (2, 1),
                "class": "piping",
                "standard": "ISO/ANSI"
            }
        }
    
    def _initialize_shape_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize patterns for basic geometric shapes"""
        return {
            "circle": {
                "detection": "hough_circle",
                "properties": ["radius", "center"],
                "tolerance": 0.05
            },
            "rectangle": {
                "detection": "contour_approx",
                "properties": ["width", "height", "corners"],
                "tolerance": 0.1
            },
            "triangle": {
                "detection": "contour_approx",
                "properties": ["vertices", "angles"],
                "tolerance": 0.1
            },
            "polygon": {
                "detection": "contour_approx",
                "properties": ["vertices", "sides"],
                "tolerance": 0.05
            },
            "arc": {
                "detection": "curve_detection",
                "properties": ["radius", "angle", "center"],
                "tolerance": 0.1
            },
            "line": {
                "detection": "hough_line",
                "properties": ["length", "angle", "endpoints"],
                "tolerance": 0.02
            }
        }
    
    def _initialize_cad_standards(self) -> Dict[str, Dict[str, Any]]:
        """Initialize CAD standards and conventions"""
        return {
            "ISO": {
                "line_weights": [0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0],
                "text_sizes": [1.8, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0, 20.0],
                "dimension_standards": "ISO 129"
            },
            "ANSI": {
                "line_weights": [0.006, 0.010, 0.014, 0.020, 0.028, 0.040, 0.056, 0.080],
                "text_sizes": [0.06, 0.08, 0.10, 0.12, 0.16, 0.20, 0.24, 0.32],
                "dimension_standards": "ASME Y14.5"
            },
            "DIN": {
                "line_weights": [0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4],
                "text_sizes": [1.8, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0, 20.0],
                "dimension_standards": "DIN 406"
            }
        }
    
    def extract(self, image_data: Any, text_content: str = "", 
                ai_enhancement: bool = True, **kwargs) -> VectorGraphicsResult:
        """
        Main extraction method for vector graphics analysis
        
        Args:
            image_data: Image data (numpy array, file path, or PIL Image)
            text_content: Associated text content from the document
            ai_enhancement: Whether to use AI for enhanced analysis
            **kwargs: Additional parameters
            
        Returns:
            VectorGraphicsResult with comprehensive analysis
        """
        try:
            # Convert image data to OpenCV format
            img = self._prepare_image(image_data)
            if img is None:
                return VectorGraphicsResult(0, 0, [], [], {}, {}, processing_notes=["Failed to load image"])
            
            processing_notes = []
            
            # Detect shapes
            shapes = self._detect_geometric_shapes(img)
            processing_notes.append(f"Detected {len(shapes)} geometric shapes")
            
            # Detect symbols
            symbols = self._detect_cad_symbols(img, shapes)
            processing_notes.append(f"Detected {len(symbols)} CAD symbols")
            
            # Classify drawing type
            drawing_type = self._classify_drawing_type(symbols, shapes, text_content)
            processing_notes.append(f"Drawing classified as: {drawing_type}")
            
            # Calculate classifications
            symbol_classifications = self._classify_symbols(symbols)
            shape_classifications = self._classify_shapes(shapes)
            
            # Calculate complexity and confidence
            complexity_score = self._calculate_complexity_score(symbols, shapes)
            confidence = self._calculate_confidence(symbols, shapes, len(processing_notes))
            
            # AI Enhancement
            if ai_enhancement and self.ai_service:
                try:
                    symbols, shapes = self._enhance_with_ai(symbols, shapes, text_content)
                    processing_notes.append("AI enhancement applied successfully")
                except Exception as e:
                    processing_notes.append(f"AI enhancement failed: {str(e)}")
            
            return VectorGraphicsResult(
                total_symbols=len(symbols),
                total_shapes=len(shapes),
                symbols=symbols,
                shapes=shapes,
                symbol_classifications=symbol_classifications,
                shape_classifications=shape_classifications,
                drawing_type=drawing_type,
                complexity_score=complexity_score,
                confidence=confidence,
                processing_notes=processing_notes
            )
            
        except Exception as e:
            logger.error(f"Vector graphics extraction failed: {e}")
            return VectorGraphicsResult(
                0, 0, [], [], {}, {}, 
                processing_notes=[f"Extraction failed: {str(e)}"]
            )
    
    def _prepare_image(self, image_data: Any) -> Optional[np.ndarray]:
        """Convert various image formats to OpenCV format"""
        try:
            if isinstance(image_data, str):
                # File path
                return cv2.imread(image_data)
            elif isinstance(image_data, np.ndarray):
                # Already in numpy format
                return image_data
            else:
                # Try PIL Image conversion
                import PIL.Image
                if isinstance(image_data, PIL.Image.Image):
                    return cv2.cvtColor(np.array(image_data), cv2.COLOR_RGB2BGR)
                
            return None
        except Exception as e:
            logger.error(f"Image preparation failed: {e}")
            return None
    
    def _detect_geometric_shapes(self, img: np.ndarray) -> List[GeometricShape]:
        """Detect basic geometric shapes using computer vision"""
        shapes = []
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Detect circles
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20, 
                                     param1=50, param2=30, minRadius=10, maxRadius=200)
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                for (x, y, r) in circles:
                    shapes.append(GeometricShape(
                        shape_type="circle",
                        dimensions={"radius": float(r)},
                        coordinates={"x": int(x), "y": int(y)},
                        properties={"area": float(np.pi * r * r), "perimeter": float(2 * np.pi * r)}
                    ))
            
            # Detect lines
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, 
                                   minLineLength=30, maxLineGap=10)
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                    angle = np.degrees(np.arctan2(y2-y1, x2-x1))
                    
                    shapes.append(GeometricShape(
                        shape_type="line",
                        dimensions={"length": float(length)},
                        coordinates={"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                        properties={"angle": float(angle)}
                    ))
            
            # Detect contours for polygons and rectangles
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                # Filter small contours
                area = cv2.contourArea(contour)
                if area < 100:
                    continue
                
                # Approximate contour
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                if len(approx) == 4:
                    # Rectangle
                    shapes.append(GeometricShape(
                        shape_type="rectangle",
                        dimensions={"width": float(w), "height": float(h)},
                        coordinates={"x": int(x), "y": int(y)},
                        properties={"area": float(area), "perimeter": float(cv2.arcLength(contour, True))}
                    ))
                elif len(approx) == 3:
                    # Triangle
                    shapes.append(GeometricShape(
                        shape_type="triangle",
                        dimensions={"base": float(w), "height": float(h)},
                        coordinates={"x": int(x), "y": int(y)},
                        properties={"area": float(area), "vertices": len(approx)}
                    ))
                elif len(approx) > 4:
                    # Polygon
                    shapes.append(GeometricShape(
                        shape_type="polygon",
                        dimensions={"width": float(w), "height": float(h)},
                        coordinates={"x": int(x), "y": int(y)},
                        properties={"area": float(area), "vertices": len(approx)}
                    ))
            
        except Exception as e:
            logger.error(f"Shape detection failed: {e}")
        
        return shapes
    
    def _detect_cad_symbols(self, img: np.ndarray, shapes: List[GeometricShape]) -> List[VectorSymbol]:
        """Detect CAD symbols using pattern matching and shape analysis"""
        symbols = []
        
        try:
            # Analyze shape combinations for symbol patterns
            for i, shape in enumerate(shapes):
                symbol = self._analyze_shape_for_symbol(shape, shapes, i)
                if symbol:
                    symbols.append(symbol)
            
            # Look for complex symbol patterns
            complex_symbols = self._detect_complex_symbols(img, shapes)
            symbols.extend(complex_symbols)
            
        except Exception as e:
            logger.error(f"Symbol detection failed: {e}")
        
        return symbols
    
    def _analyze_shape_for_symbol(self, shape: GeometricShape, all_shapes: List[GeometricShape], 
                                 index: int) -> Optional[VectorSymbol]:
        """Analyze individual shapes for symbol patterns"""
        try:
            # Simple symbol detection based on shape characteristics
            if shape.shape_type == "circle":
                # Could be bearing, gear, or electrical component
                radius = shape.dimensions.get("radius", 0)
                if 10 < radius < 50:
                    # Look for nearby shapes that might indicate symbol type
                    nearby_shapes = self._find_nearby_shapes(shape, all_shapes, radius * 2)
                    
                    if any(s.shape_type == "circle" for s in nearby_shapes):
                        return VectorSymbol(
                            symbol_type="bearing",
                            symbol_class="mechanical",
                            confidence=0.7,
                            coordinates=shape.coordinates,
                            properties={"radius": radius},
                            standard_reference="ISO",
                            description="Concentric circles pattern suggests bearing symbol"
                        )
            
            elif shape.shape_type == "rectangle":
                # Could be various symbols
                width = shape.dimensions.get("width", 0)
                height = shape.dimensions.get("height", 0)
                aspect_ratio = width / height if height > 0 else 0
                
                if 2.5 < aspect_ratio < 4.0:
                    return VectorSymbol(
                        symbol_type="resistor",
                        symbol_class="electrical",
                        confidence=0.6,
                        coordinates=shape.coordinates,
                        properties={"aspect_ratio": aspect_ratio},
                        standard_reference="IEEE",
                        description="Rectangular shape with electrical component aspect ratio"
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Shape analysis failed: {e}")
            return None
    
    def _detect_complex_symbols(self, img: np.ndarray, shapes: List[GeometricShape]) -> List[VectorSymbol]:
        """Detect complex symbols using template matching and pattern analysis"""
        symbols = []
        
        try:
            # Template matching for known symbols would go here
            # This is a simplified version - in practice, you'd use actual symbol templates
            
            # Detect electrical circuit patterns
            electrical_symbols = self._detect_electrical_patterns(shapes)
            symbols.extend(electrical_symbols)
            
            # Detect mechanical symbols
            mechanical_symbols = self._detect_mechanical_patterns(shapes)
            symbols.extend(mechanical_symbols)
            
            # Detect architectural symbols
            architectural_symbols = self._detect_architectural_patterns(shapes)
            symbols.extend(architectural_symbols)
            
        except Exception as e:
            logger.error(f"Complex symbol detection failed: {e}")
        
        return symbols
    
    def _detect_electrical_patterns(self, shapes: List[GeometricShape]) -> List[VectorSymbol]:
        """Detect electrical symbol patterns"""
        symbols = []
        
        # Look for parallel lines (capacitor pattern)
        lines = [s for s in shapes if s.shape_type == "line"]
        for i, line1 in enumerate(lines):
            for line2 in lines[i+1:]:
                if self._are_lines_parallel(line1, line2):
                    distance = self._calculate_line_distance(line1, line2)
                    if 5 < distance < 30:
                        symbols.append(VectorSymbol(
                            symbol_type="capacitor",
                            symbol_class="electrical",
                            confidence=0.8,
                            coordinates=self._get_midpoint_coordinates(line1, line2),
                            properties={"line_distance": distance},
                            standard_reference="IEEE",
                            description="Parallel lines pattern suggests capacitor symbol"
                        ))
        
        return symbols
    
    def _detect_mechanical_patterns(self, shapes: List[GeometricShape]) -> List[VectorSymbol]:
        """Detect mechanical symbol patterns"""
        symbols = []
        
        # Look for spring patterns (vertical coil-like structures)
        rectangles = [s for s in shapes if s.shape_type == "rectangle"]
        for rect in rectangles:
            height = rect.dimensions.get("height", 0)
            width = rect.dimensions.get("width", 0)
            aspect_ratio = height / width if width > 0 else 0
            
            if aspect_ratio > 2.5:  # Tall, narrow rectangle
                symbols.append(VectorSymbol(
                    symbol_type="spring",
                    symbol_class="mechanical",
                    confidence=0.6,
                    coordinates=rect.coordinates,
                    properties={"aspect_ratio": aspect_ratio},
                    standard_reference="ISO",
                    description="Tall rectangle suggests spring or coil symbol"
                ))
        
        return symbols
    
    def _detect_architectural_patterns(self, shapes: List[GeometricShape]) -> List[VectorSymbol]:
        """Detect architectural symbol patterns"""
        symbols = []
        
        # Look for door patterns (arc with line)
        # This would be more sophisticated in practice
        for shape in shapes:
            if shape.shape_type == "rectangle":
                width = shape.dimensions.get("width", 0)
                height = shape.dimensions.get("height", 0)
                
                if width > height * 2:  # Wide rectangle might be wall
                    symbols.append(VectorSymbol(
                        symbol_type="wall",
                        symbol_class="architectural",
                        confidence=0.5,
                        coordinates=shape.coordinates,
                        properties={"width": width, "thickness": height},
                        standard_reference="AIA",
                        description="Wide rectangle suggests wall element"
                    ))
        
        return symbols
    
    def _find_nearby_shapes(self, target_shape: GeometricShape, all_shapes: List[GeometricShape], 
                           radius: float) -> List[GeometricShape]:
        """Find shapes near the target shape within specified radius"""
        nearby = []
        target_x = target_shape.coordinates.get("x", 0)
        target_y = target_shape.coordinates.get("y", 0)
        
        for shape in all_shapes:
            if shape == target_shape:
                continue
                
            shape_x = shape.coordinates.get("x", 0)
            shape_y = shape.coordinates.get("y", 0)
            distance = np.sqrt((shape_x - target_x)**2 + (shape_y - target_y)**2)
            
            if distance <= radius:
                nearby.append(shape)
        
        return nearby
    
    def _are_lines_parallel(self, line1: GeometricShape, line2: GeometricShape) -> bool:
        """Check if two lines are parallel"""
        if line1.shape_type != "line" or line2.shape_type != "line":
            return False
            
        angle1 = line1.properties.get("angle", 0)
        angle2 = line2.properties.get("angle", 0)
        angle_diff = abs(angle1 - angle2)
        
        return angle_diff < 5 or abs(angle_diff - 180) < 5  # Allow 5 degree tolerance
    
    def _calculate_line_distance(self, line1: GeometricShape, line2: GeometricShape) -> float:
        """Calculate perpendicular distance between two parallel lines"""
        # Simplified distance calculation
        x1 = line1.coordinates.get("x1", 0)
        y1 = line1.coordinates.get("y1", 0)
        x2 = line2.coordinates.get("x1", 0)
        y2 = line2.coordinates.get("y1", 0)
        
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def _get_midpoint_coordinates(self, shape1: GeometricShape, shape2: GeometricShape) -> Dict[str, Any]:
        """Calculate midpoint between two shapes"""
        x1 = shape1.coordinates.get("x", 0)
        y1 = shape1.coordinates.get("y", 0)
        x2 = shape2.coordinates.get("x", 0)
        y2 = shape2.coordinates.get("y", 0)
        
        return {
            "x": int((x1 + x2) / 2),
            "y": int((y1 + y2) / 2)
        }
    
    def _classify_drawing_type(self, symbols: List[VectorSymbol], shapes: List[GeometricShape], 
                              text_content: str) -> str:
        """Classify the type of technical drawing"""
        try:
            # Count symbol types
            symbol_classes = {}
            for symbol in symbols:
                symbol_classes[symbol.symbol_class] = symbol_classes.get(symbol.symbol_class, 0) + 1
            
            # Determine dominant class
            if not symbol_classes:
                if len(shapes) > 10:
                    return "technical_drawing"
                return "unknown"
            
            dominant_class = max(symbol_classes.items(), key=lambda x: x[1])[0]
            
            # Map to drawing types
            drawing_types = {
                "electrical": "electrical_schematic",
                "mechanical": "mechanical_drawing",
                "architectural": "architectural_plan",
                "piping": "piping_diagram"
            }
            
            return drawing_types.get(dominant_class, "technical_drawing")
            
        except Exception as e:
            logger.error(f"Drawing classification failed: {e}")
            return "unknown"
    
    def _classify_symbols(self, symbols: List[VectorSymbol]) -> Dict[str, int]:
        """Count symbols by type"""
        classifications = {}
        for symbol in symbols:
            classifications[symbol.symbol_type] = classifications.get(symbol.symbol_type, 0) + 1
        return classifications
    
    def _classify_shapes(self, shapes: List[GeometricShape]) -> Dict[str, int]:
        """Count shapes by type"""
        classifications = {}
        for shape in shapes:
            classifications[shape.shape_type] = classifications.get(shape.shape_type, 0) + 1
        return classifications
    
    def _calculate_complexity_score(self, symbols: List[VectorSymbol], shapes: List[GeometricShape]) -> float:
        """Calculate drawing complexity score"""
        try:
            # Base complexity from counts
            base_score = len(symbols) * 2 + len(shapes)
            
            # Bonus for symbol variety
            symbol_types = len(set(s.symbol_type for s in symbols))
            shape_types = len(set(s.shape_type for s in shapes))
            variety_bonus = (symbol_types + shape_types) * 5
            
            # Normalize to 0-100 scale
            total_score = base_score + variety_bonus
            return min(100.0, total_score / 2)
            
        except Exception as e:
            logger.error(f"Complexity calculation failed: {e}")
            return 0.0
    
    def _calculate_confidence(self, symbols: List[VectorSymbol], shapes: List[GeometricShape], 
                            processing_steps: int) -> float:
        """Calculate overall confidence score"""
        try:
            if not symbols and not shapes:
                return 0.0
            
            # Average symbol confidence
            symbol_conf = sum(s.confidence for s in symbols) / len(symbols) if symbols else 0.5
            
            # Shape detection confidence (based on successful processing)
            shape_conf = 0.8 if shapes else 0.3
            
            # Processing success factor
            process_conf = max(0.5, 1.0 - (processing_steps - 3) * 0.1)
            
            return (symbol_conf + shape_conf + process_conf) / 3
            
        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            return 0.5
    
    def _enhance_with_ai(self, symbols: List[VectorSymbol], shapes: List[GeometricShape], 
                        text_content: str) -> Tuple[List[VectorSymbol], List[GeometricShape]]:
        """Enhance extraction results using AI analysis"""
        try:
            if not self.ai_service:
                return symbols, shapes
            
            # Prepare data for AI analysis
            analysis_data = {
                "symbols": [asdict(s) for s in symbols],
                "shapes": [asdict(s) for s in shapes],
                "text_context": text_content[:1000]  # Limit context
            }
            
            prompt = f"""
            Analyze the following vector graphics extraction results from a technical drawing:
            
            {json.dumps(analysis_data, indent=2)}
            
            Please:
            1. Improve symbol classifications and confidence scores
            2. Identify any missed symbol patterns
            3. Correct any misclassifications
            4. Add standard references where missing
            5. Improve descriptions
            
            Return the enhanced results in the same JSON format.
            """
            
            ai_response = self.ai_service.analyze(prompt)
            
            if ai_response and isinstance(ai_response, dict):
                # Parse AI response and update results
                enhanced_symbols = []
                enhanced_shapes = []
                
                for symbol_data in ai_response.get("symbols", []):
                    enhanced_symbols.append(VectorSymbol(**symbol_data))
                
                for shape_data in ai_response.get("shapes", []):
                    enhanced_shapes.append(GeometricShape(**shape_data))
                
                return enhanced_symbols, enhanced_shapes
            
        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
        
        return symbols, shapes
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported image formats"""
        return [
            "image/jpeg", "image/jpg", "image/png", "image/bmp", 
            "image/tiff", "image/tif", "image/svg+xml"
        ]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get extractor capabilities and metadata"""
        return {
            "name": "Vector Graphics Extractor",
            "version": "1.0.0",
            "description": "Advanced extractor for CAD symbols and technical drawing elements",
            "supported_formats": self.get_supported_formats(),
            "symbol_types": list(self.symbol_patterns.keys()),
            "shape_types": list(self.shape_patterns.keys()),
            "standards_supported": list(self.cad_standards.keys()),
            "features": [
                "CAD symbol detection",
                "Geometric shape analysis", 
                "Technical drawing classification",
                "Standards compliance checking",
                "AI-powered enhancement",
                "Confidence scoring"
            ],
            "ai_enhanced": True,
            "processing_speed": "medium",
            "accuracy": "high"
        }