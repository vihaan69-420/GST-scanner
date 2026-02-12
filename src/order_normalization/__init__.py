"""
Order Upload & Normalization Module (Epic 2)
Handles handwritten order processing, normalization, pricing matching, and PDF generation

This module is feature-flagged and completely isolated from existing GST scanner flows.
"""
import config

# Feature flag check - only export if feature is enabled
if config.FEATURE_ORDER_UPLOAD_NORMALIZATION:
    from .order_session import OrderSession
    from .orchestrator import OrderNormalizationOrchestrator
    from .extractor import OrderExtractor
    from .normalizer import OrderNormalizer
    from .deduplicator import OrderDeduplicator
    from .pricing_matcher import PricingMatcher
    from .pdf_generator import OrderPDFGenerator
    from .sheets_handler import OrderSheetsHandler
    
    __all__ = [
        'OrderSession',
        'OrderNormalizationOrchestrator',
        'OrderExtractor',
        'OrderNormalizer',
        'OrderDeduplicator',
        'PricingMatcher',
        'OrderPDFGenerator',
        'OrderSheetsHandler',
    ]
else:
    __all__ = []
