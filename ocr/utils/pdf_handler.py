import os
from PIL import Image
import pypdfium2 as pdfium

def pdf_to_images(pdf_path, output_dir=None):
    """
    Convert a PDF file to a list of PIL Images.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    pdf = pdfium.PdfDocument(pdf_path)
    images = []
    
    for page_indices in range(len(pdf)):
        page = pdf[page_indices]
        bitmap = page.render(
            scale=4,  # Increased to 4 (approx 300 DPI) for high-precision OCR
            rotation=0,
        )
        pil_image = bitmap.to_pil()
        images.append(pil_image)
        
        if output_dir:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            image_path = os.path.join(output_dir, f"page_{page_indices + 1}.png")
            pil_image.save(image_path)
            
    return images
