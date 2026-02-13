import os
import pypdfium2 as pdfium

def pdf_to_images(pdf_path, output_dir=None):
    """
    Convert a PDF file to a list of PIL Images sequentially.
    Sequential is safer for PDFium's underlying C library.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    pdf = pdfium.PdfDocument(pdf_path)
    num_pages = len(pdf)
    images = []
    
    render_scale = float(os.getenv("PDF_RENDER_SCALE", "3"))
    render_scale = max(1.5, min(4.0, render_scale))

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    for i in range(num_pages):
        page = pdf[i]
        bitmap = page.render(
            scale=render_scale,
            rotation=0,
        )
        pil_image = bitmap.to_pil()
        images.append(pil_image)
        
        if output_dir:
            image_path = os.path.join(output_dir, f"page_{i + 1}.png")
            pil_image.save(image_path)
            
    pdf.close()
    return images
