"""
Pricing Calculator for GST Scanner
Calculates API costs based on configurable pricing from config
"""
import config
from typing import Dict, Optional


class PricingCalculator:
    """Calculate API costs based on token usage and configurable pricing"""
    
    def __init__(self):
        """Initialize with pricing from config"""
        self.ocr_price_per_1k = config.GEMINI_OCR_PRICE_PER_1K_TOKENS
        self.parsing_price_per_1k = config.GEMINI_PARSING_PRICE_PER_1K_TOKENS
    
    def calculate_ocr_cost(self, tokens: int) -> float:
        """
        Calculate cost for OCR (Vision API) call
        
        Args:
            tokens: Total token count
        
        Returns:
            Cost in USD
        """
        return (tokens / 1000) * self.ocr_price_per_1k
    
    def calculate_parsing_cost(self, tokens: int) -> float:
        """
        Calculate cost for parsing (Text API) call
        
        Args:
            tokens: Total token count
        
        Returns:
            Cost in USD
        """
        return (tokens / 1000) * self.parsing_price_per_1k
    
    def calculate_invoice_cost(
        self,
        ocr_tokens: int,
        parsing_tokens: int
    ) -> Dict[str, float]:
        """
        Calculate total cost for an invoice
        
        Args:
            ocr_tokens: Total OCR tokens
            parsing_tokens: Total parsing tokens
        
        Returns:
            Dict with cost breakdown
        """
        ocr_cost = self.calculate_ocr_cost(ocr_tokens)
        parsing_cost = self.calculate_parsing_cost(parsing_tokens)
        
        return {
            'ocr_cost_usd': round(ocr_cost, 6),
            'parsing_cost_usd': round(parsing_cost, 6),
            'total_cost_usd': round(ocr_cost + parsing_cost, 6)
        }
    
    def get_pricing_info(self) -> Dict[str, float]:
        """
        Get current pricing configuration
        
        Returns:
            Dict with pricing rates
        """
        return {
            'ocr_price_per_1k_tokens': self.ocr_price_per_1k,
            'parsing_price_per_1k_tokens': self.parsing_price_per_1k
        }


# Global instance
_pricing_calculator = None

def get_pricing_calculator() -> PricingCalculator:
    """Get or create global pricing calculator instance"""
    global _pricing_calculator
    if _pricing_calculator is None:
        _pricing_calculator = PricingCalculator()
    return _pricing_calculator


if __name__ == "__main__":
    # Test the pricing calculator
    calc = get_pricing_calculator()
    
    print("\n" + "="*80)
    print("Testing Pricing Calculator")
    print("="*80 + "\n")
    
    # Print current pricing
    pricing = calc.get_pricing_info()
    print(f"Current Pricing:")
    print(f"  OCR: ${pricing['ocr_price_per_1k_tokens']:.6f} per 1K tokens")
    print(f"  Parsing: ${pricing['parsing_price_per_1k_tokens']:.6f} per 1K tokens")
    print()
    
    # Test invoice cost calculation
    ocr_tokens = 5801
    parsing_tokens = 1650
    
    costs = calc.calculate_invoice_cost(ocr_tokens, parsing_tokens)
    
    print(f"Example Invoice Cost Calculation:")
    print(f"  OCR Tokens: {ocr_tokens:,}")
    print(f"  Parsing Tokens: {parsing_tokens:,}")
    print(f"  Total Tokens: {ocr_tokens + parsing_tokens:,}")
    print()
    print(f"  OCR Cost: ${costs['ocr_cost_usd']:.6f}")
    print(f"  Parsing Cost: ${costs['parsing_cost_usd']:.6f}")
    print(f"  Total Cost: ${costs['total_cost_usd']:.6f}")
    print()
    print("="*80)
