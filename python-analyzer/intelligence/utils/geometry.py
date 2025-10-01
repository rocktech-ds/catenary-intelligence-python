"""
Geometry Utilities
Vector and geometric calculations for PDF analysis, especially callout detection
"""
import math
from typing import List, Tuple, Optional, Union
from dataclasses import dataclass

@dataclass
class Point:
    """2D Point representation"""
    x: float
    y: float
    
    def distance_to(self, other: 'Point') -> float:
        """Calculate Euclidean distance to another point"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)
    
    def __add__(self, other: 'Point') -> 'Point':
        return Point(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other: 'Point') -> 'Point':
        return Point(self.x - other.x, self.y - other.y)
    
    def __mul__(self, scalar: float) -> 'Point':
        return Point(self.x * scalar, self.y * scalar)

@dataclass 
class Line:
    """2D Line segment representation"""
    start: Point
    end: Point
    
    @property
    def length(self) -> float:
        """Calculate line length"""
        return self.start.distance_to(self.end)
    
    @property
    def angle(self) -> float:
        """Calculate line angle in radians"""
        return math.atan2(self.end.y - self.start.y, self.end.x - self.start.x)
    
    @property
    def midpoint(self) -> Point:
        """Calculate midpoint of line"""
        return Point((self.start.x + self.end.x) / 2, (self.start.y + self.end.y) / 2)
    
    def direction_vector(self) -> Point:
        """Get normalized direction vector"""
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        length = self.length
        if length == 0:
            return Point(0, 0)
        return Point(dx / length, dy / length)

@dataclass
class BoundingBox:
    """Rectangle bounding box"""
    x0: float
    y0: float
    x1: float
    y1: float
    
    @property
    def width(self) -> float:
        return abs(self.x1 - self.x0)
    
    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Point:
        return Point((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)
    
    def contains_point(self, point: Point) -> bool:
        """Check if point is inside bounding box"""
        return (min(self.x0, self.x1) <= point.x <= max(self.x0, self.x1) and
                min(self.y0, self.y1) <= point.y <= max(self.y0, self.y1))
    
    def intersects(self, other: 'BoundingBox') -> bool:
        """Check if this bbox intersects with another"""
        return not (self.x1 < other.x0 or other.x1 < self.x0 or
                   self.y1 < other.y0 or other.y1 < self.y0)
    
    def intersection_area(self, other: 'BoundingBox') -> float:
        """Calculate intersection area with another bounding box"""
        if not self.intersects(other):
            return 0.0
        
        x_left = max(min(self.x0, self.x1), min(other.x0, other.x1))
        y_top = max(min(self.y0, self.y1), min(other.y0, other.y1))
        x_right = min(max(self.x0, self.x1), max(other.x0, other.x1))
        y_bottom = min(max(self.y0, self.y1), max(other.y0, other.y1))
        
        return (x_right - x_left) * (y_bottom - y_top)
    
    def iou(self, other: 'BoundingBox') -> float:
        """Calculate Intersection over Union (IoU) with another bbox"""
        intersection = self.intersection_area(other)
        if intersection == 0:
            return 0.0
        
        union = self.area + other.area - intersection
        return intersection / union if union > 0 else 0.0

def point_to_line_distance(point: Point, line: Line) -> float:
    """Calculate perpendicular distance from point to line"""
    # Line from start to end
    A = line.end.y - line.start.y
    B = line.start.x - line.end.x  
    C = line.end.x * line.start.y - line.start.x * line.end.y
    
    # Distance formula: |Ax + By + C| / sqrt(A² + B²)
    denominator = math.sqrt(A * A + B * B)
    if denominator == 0:
        return point.distance_to(line.start)
    
    return abs(A * point.x + B * point.y + C) / denominator

def find_nearest_point_on_line(point: Point, line: Line) -> Point:
    """Find the nearest point on a line to a given point"""
    # Vector from line start to point
    ap = point - line.start
    # Vector from line start to end
    ab = line.end - line.start
    
    # Project ap onto ab
    ab_length_sq = ab.x * ab.x + ab.y * ab.y
    if ab_length_sq == 0:
        return line.start
    
    t = max(0, min(1, (ap.x * ab.x + ap.y * ab.y) / ab_length_sq))
    
    # Return the projected point
    return line.start + ab * t

def angle_between_lines(line1: Line, line2: Line) -> float:
    """Calculate angle between two lines in radians"""
    angle1 = line1.angle
    angle2 = line2.angle
    diff = abs(angle1 - angle2)
    return min(diff, 2 * math.pi - diff)

def is_arrow_line(line: Line, min_length: float = 10.0) -> bool:
    """Determine if a line could be an arrow/leader line"""
    return line.length >= min_length

def find_text_near_point(point: Point, text_elements: List[dict], max_distance: float = 40.0) -> List[dict]:
    """Find text elements near a point"""
    nearby_text = []
    
    for element in text_elements:
        # Assume text elements have 'bbox' with x0, y0, x1, y1
        bbox = element.get('bbox', {})
        if not bbox:
            continue
            
        # Calculate text center
        text_center = Point(
            (bbox.get('x0', 0) + bbox.get('x1', 0)) / 2,
            (bbox.get('y0', 0) + bbox.get('y1', 0)) / 2
        )
        
        distance = point.distance_to(text_center)
        if distance <= max_distance:
            nearby_text.append({
                'element': element,
                'distance': distance,
                'center': text_center
            })
    
    # Sort by distance
    nearby_text.sort(key=lambda x: x['distance'])
    return nearby_text

def detect_arrow_direction(line: Line) -> str:
    """Detect arrow direction based on line angle"""
    angle_deg = math.degrees(line.angle)
    
    # Normalize angle to 0-360 range
    if angle_deg < 0:
        angle_deg += 360
    
    if 315 <= angle_deg or angle_deg < 45:
        return 'right'
    elif 45 <= angle_deg < 135:
        return 'down'
    elif 135 <= angle_deg < 225:
        return 'left'
    else:
        return 'up'

def group_nearby_lines(lines: List[Line], max_distance: float = 5.0) -> List[List[Line]]:
    """Group lines that are close to each other (for complex arrows)"""
    if not lines:
        return []
    
    groups = []
    used = set()
    
    for i, line in enumerate(lines):
        if i in used:
            continue
            
        group = [line]
        used.add(i)
        
        for j, other_line in enumerate(lines):
            if j in used or i == j:
                continue
                
            # Check if lines are close enough
            min_dist = float('inf')
            for point in [line.start, line.end]:
                for other_point in [other_line.start, other_line.end]:
                    dist = point.distance_to(other_point)
                    min_dist = min(min_dist, dist)
            
            if min_dist <= max_distance:
                group.append(other_line)
                used.add(j)
        
        groups.append(group)
    
    return groups

def calculate_line_intersection(line1: Line, line2: Line) -> Optional[Point]:
    """Calculate intersection point of two lines (if they intersect)"""
    x1, y1 = line1.start.x, line1.start.y
    x2, y2 = line1.end.x, line1.end.y
    x3, y3 = line2.start.x, line2.start.y
    x4, y4 = line2.end.x, line2.end.y
    
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    
    if abs(denominator) < 1e-10:  # Lines are parallel
        return None
    
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominator
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denominator
    
    if 0 <= t <= 1 and 0 <= u <= 1:  # Intersection within both line segments
        intersection_x = x1 + t * (x2 - x1)
        intersection_y = y1 + t * (y2 - y1)
        return Point(intersection_x, intersection_y)
    
    return None

def create_expanded_bbox(bbox: BoundingBox, margin: float) -> BoundingBox:
    """Create a bounding box expanded by a margin"""
    return BoundingBox(
        bbox.x0 - margin,
        bbox.y0 - margin,
        bbox.x1 + margin,
        bbox.y1 + margin
    )

def filter_lines_by_length(lines: List[Line], min_length: float = 10.0, max_length: float = 200.0) -> List[Line]:
    """Filter lines by length criteria"""
    return [line for line in lines if min_length <= line.length <= max_length]

def detect_arrow_pattern(lines: List[Line], tolerance: float = 10.0) -> List[dict]:
    """Detect arrow patterns from a collection of lines"""
    arrows = []
    
    # Group nearby lines
    groups = group_nearby_lines(lines, tolerance)
    
    for group in groups:
        if len(group) == 1:
            # Single line arrow
            line = group[0]
            if is_arrow_line(line):
                arrows.append({
                    'type': 'simple',
                    'main_line': line,
                    'direction': detect_arrow_direction(line),
                    'tip_point': line.end  # Assume end is the tip
                })
        
        elif len(group) >= 2:
            # Multi-line arrow (with arrowhead)
            # Find the longest line as main shaft
            main_line = max(group, key=lambda l: l.length)
            other_lines = [l for l in group if l != main_line]
            
            arrows.append({
                'type': 'complex',
                'main_line': main_line,
                'head_lines': other_lines,
                'direction': detect_arrow_direction(main_line),
                'tip_point': main_line.end
            })
    
    return arrows

def calculate_text_line_association_score(text_bbox: BoundingBox, line: Line) -> float:
    """Calculate how likely a text element is associated with a line/arrow"""
    text_center = text_bbox.center
    
    # Distance to line endpoints
    start_dist = text_center.distance_to(line.start)
    end_dist = text_center.distance_to(line.end)
    
    # Distance to line itself
    line_dist = point_to_line_distance(text_center, line)
    
    # Score based on proximity (closer = higher score)
    min_endpoint_dist = min(start_dist, end_dist)
    
    # Prefer text near line endpoints
    score = 1.0 / (1.0 + min_endpoint_dist * 0.1)  # Scale factor
    
    # Bonus if text is very close to the line
    if line_dist < 20.0:
        score *= 1.5
    
    # Penalty if text is far from line
    if min_endpoint_dist > 100.0:
        score *= 0.1
    
    return max(0.0, min(1.0, score))