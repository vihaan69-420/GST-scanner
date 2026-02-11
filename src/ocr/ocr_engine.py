"""
OCR Engine using Google Gemini Vision API
Handles image processing and text extraction
"""
import os
import google.generativeai as genai
from typing import List, Dict
from PIL import Image
import config


class OCREngine:
    """OCR Engine using Google Gemini Vision API for invoice text extraction"""
    
    def __init__(self, metrics_tracker=None, logger=None):
        """Initialize the OCR engine with Gemini API"""
        genai.configure(api_key=config.GOOGLE_API_KEY)
        
        # Use Gemini 2.5 Flash for fast, cost-effective vision processing
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Optional monitoring (for compatibility with GST-scanner structure)
        self.metrics_tracker = metrics_tracker
        self.logger = logger
        
        # OCR prompt for complete text extraction
        self.ocr_prompt = """
Extract ALL visible text from this invoice image with 100% accuracy.

INSTRUCTIONS:
1. Scan the ENTIRE image from top to bottom, left to right
2. Extract EVERY piece of text including:
   - Headers, titles, and labels
   - Company names and addresses
   - Invoice numbers, dates, and references
   - All table contents (row by row, column by column)
   - GST numbers, tax details, and totals
   - Bank details, UPI IDs, and payment info
   - Terms, conditions, declarations, and signatures
   - All numerical values, percentages, and amounts
3. Preserve the layout structure (tables, sections)
4. Do NOT summarize or skip any text
5. Do NOT calculate or interpret - just extract exactly what you see
6. If text is unclear, provide your best reading

OUTPUT FORMAT:
Plain text, preserving structure and line breaks.
"""
    
    def extract_text_from_image(self, image_path: str) -> Dict:
        """
        Extract text from a single invoice image
        
        Args:
            image_path: Path to the invoice image
            
        Returns:
            Dict with 'text' and optional 'usage_metadata'
        """
        try:
            # Load and validate image
            image = Image.open(image_path)
            
            # Generate content using Gemini Vision
            response = self.model.generate_content([self.ocr_prompt, image])
            
            # Extract text from response
            extracted_text = response.text if response.text else ""
            
            # ═══════════════════════════════════════════════════════
            # NEW: Capture token usage metadata (Phase 2)
            # ═══════════════════════════════════════════════════════
            result = {'text': extracted_text}
            
            # Capture actual token usage from API response
            if config.ENABLE_USAGE_TRACKING and config.ENABLE_ACTUAL_TOKEN_CAPTURE:
                if hasattr(response, 'usage_metadata'):
                    result['usage_metadata'] = {
                        'prompt_tokens': response.usage_metadata.prompt_token_count if hasattr(response.usage_metadata, 'prompt_token_count') else 0,
                        'output_tokens': response.usage_metadata.candidates_token_count if hasattr(response.usage_metadata, 'candidates_token_count') else 0,
                        'total_tokens': response.usage_metadata.total_token_count if hasattr(response.usage_metadata, 'total_token_count') else 0
                    }
            # ═══════════════════════════════════════════════════════
            
            return result
            
        except Exception as e:
            raise Exception(f"OCR failed for {image_path}: {str(e)}")
    
    def extract_text_from_images(self, image_paths: List[str]) -> Dict:
        """
        Extract text from multiple invoice images (multi-page invoice)
        
        Args:
            image_paths: List of paths to invoice images
            
        Returns:
            Dict with 'text' (combined) and 'pages_metadata' (per-page usage)
        """
        all_text = []
        pages_metadata = []
        
        for idx, image_path in enumerate(image_paths, 1):
            try:
                print(f"Processing page {idx}/{len(image_paths)}: {os.path.basename(image_path)}")
                
                result = self.extract_text_from_image(image_path)
                page_text = result['text']
                
                # Add page separator for multi-page invoices
                if len(image_paths) > 1:
                    all_text.append(f"\n{'='*80}\n[PAGE {idx}]\n{'='*80}\n")
                
                all_text.append(page_text)
                
                # ═══════════════════════════════════════════════════════
                # NEW: Collect usage metadata per page (Phase 2)
                # ═══════════════════════════════════════════════════════
                if 'usage_metadata' in result:
                    page_metadata = result['usage_metadata'].copy()
                    page_metadata['page_number'] = idx
                    page_metadata['image_path'] = image_path
                    page_metadata['image_size_bytes'] = os.path.getsize(image_path)
                    pages_metadata.append(page_metadata)
                # ═══════════════════════════════════════════════════════
                
            except Exception as e:
                print(f"Warning: Failed to process {image_path}: {str(e)}")
                all_text.append(f"\n[ERROR: Page {idx} could not be processed]\n")
        
        # Combine all pages
        combined_text = "\n".join(all_text)
        
        return {
            'text': combined_text,
            'pages_metadata': pages_metadata
        }


if __name__ == "__main__":
    # Test the OCR engine
    ocr = OCREngine()
    
    test_image = r"c:\Users\clawd bot\Documents\saket worksflow\Sample Invoices\6321338506004860481.jpg"
    
    if os.path.exists(test_image):
        print("Testing OCR on sample invoice...")
        text = ocr.extract_text_from_image(test_image)
        print("\n" + "="*80)
        print("EXTRACTED TEXT:")
        print("="*80)
        print(text)
    else:
        print(f"Test image not found: {test_image}")
