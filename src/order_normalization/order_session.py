"""
Order Session Management
Manages the lifecycle of order processing sessions
"""
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class OrderStatus(Enum):
    """Order processing status"""
    CREATED = 'created'
    UPLOADING = 'uploading'
    SUBMITTED = 'submitted'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REVIEW_REQUIRED = 'review_required'


class OrderSession:
    """Manages order session state and lifecycle"""
    
    def __init__(self, user_id: int, username: str = None):
        """
        Initialize a new order session
        
        Args:
            user_id: Telegram user ID
            username: Telegram username (optional)
        """
        self.order_id = self._generate_order_id()
        self.user_id = user_id
        self.username = username
        self.status = OrderStatus.CREATED
        self.pages = []  # List of page dictionaries
        self.created_at = datetime.now()
        self.submitted_at = None
        self.completed_at = None
        self.error = None
        self.warning = None
        self.result = None  # Will store clean invoice data
        self.last_button_message_id = None  # Track message with Submit button
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"ORD_{timestamp}"
    
    def add_page(self, image_path: str) -> int:
        """
        Add a page to the order
        
        Args:
            image_path: Path to uploaded image
            
        Returns:
            Page number (1-indexed)
        """
        page_number = len(self.pages) + 1
        self.pages.append({
            'page_number': page_number,
            'image_path': image_path,
            'uploaded_at': datetime.now()
        })
        self.status = OrderStatus.UPLOADING
        return page_number
    
    def submit(self) -> bool:
        """
        Submit order for processing
        
        Returns:
            True if successfully submitted, False if invalid state
        """
        if not self.pages:
            return False
        
        if self.status in (OrderStatus.SUBMITTED, OrderStatus.PROCESSING, OrderStatus.COMPLETED):
            return False  # Already submitted
        
        self.status = OrderStatus.SUBMITTED
        self.submitted_at = datetime.now()
        return True
    
    def set_processing(self):
        """Mark order as processing"""
        self.status = OrderStatus.PROCESSING
    
    def set_completed(self, result: Dict):
        """
        Mark order as completed
        
        Args:
            result: Clean invoice data dictionary
        """
        self.status = OrderStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result
    
    def set_failed(self, error: str):
        """
        Mark order as failed
        
        Args:
            error: Error message
        """
        self.status = OrderStatus.FAILED
        self.error = error
    
    def set_review_required(self, warning: str):
        """
        Mark order for review
        
        Args:
            warning: Warning message
        """
        self.status = OrderStatus.REVIEW_REQUIRED
        self.warning = warning
    
    def to_dict(self) -> Dict:
        """Convert session to dictionary"""
        return {
            'order_id': self.order_id,
            'user_id': self.user_id,
            'username': self.username,
            'status': self.status.value,
            'page_count': len(self.pages),
            'pages': self.pages,
            'created_at': self.created_at,
            'submitted_at': self.submitted_at,
            'completed_at': self.completed_at,
            'error': self.error,
            'warning': self.warning,
            'result': self.result
        }
