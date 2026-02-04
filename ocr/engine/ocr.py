import os
import base64
import httpx
import re
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

class OCREngine:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.model_id = os.getenv("OCR_MODEL_ID", "deepseek-ai/DeepSeek-OCR")

    def _encode_image(self, image):
        if image.mode != 'RGB':
            image = image.convert('RGB')
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=95)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_vlm_api(self, payload):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()

    def process_image(self, image):
        """
        利用多模态模型将图片全量转化为 Markdown 格式，并输出区域坐标。
        """
        base64_image = self._encode_image(image)
        
        prompt_text = """你现在的身份是一个高精度【视觉文档分析师】。请对图片进行全要素识别和 1:1 数字化转录。

1. 【全要素坐标标记】：在回复的最开头，先输出页面中所有关键区域的坐标，格式统一为 [Type, x1, y1, x2, y2]。
   - 识别目标包括：
     * [Table]：所有表格区域。
     * [Figure]：所有图表、架构图、流程图、插图区域。
     * [Text]：关键的文本段落或标题块。
   - 坐标说明：使用 0-1000 的归一化坐标系。

2. 【1:1 无损转录】：
   - 紧接坐标之后，输出完整的 Markdown 内容。
   - 严禁翻译，保持原始语言。
   - 遇到表格：转为标准 Markdown 表格。
   - 遇到图表/架构图：描述其核心逻辑或包含的文字。
   - 普通文本：按阅读顺序完整转录。

3. 【严禁总结】：不要输出"图中显示了..."等废话，直接输出内容。"""

        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "stream": False,
            "temperature": 0.0
        }

        try:
            result = self._call_vlm_api(payload)
            full_text = result['choices'][0]['message']['content']
            # print(f"[Debug] Raw VLM Output: {full_text[:300]}...") # Debug log

            
            # 坐标提取解析：匹配任何字母构成的类型标签
            boxes = []
            
            # 兼容两种格式：
            # 1. [Type, x1, y1, x2, y2]
            # 2. <|ref|>Type<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
            
            # 格式 1
            coord_patterns = re.findall(r"\[([a-zA-Z]+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]", full_text)
            for m in coord_patterns:
                try:
                    boxes.append({
                        "type": m[0].strip(),
                        "x": int(m[1]) / 10, "y": int(m[2]) / 10,
                        "w": (int(m[3]) - int(m[1])) / 10, "h": (int(m[4]) - int(m[2])) / 10
                    })
                except: continue

            # 格式 2 (DeepSeek/Qwen VL Style)
            grounding_patterns = re.findall(r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>", full_text)
            for m in grounding_patterns:
                try:
                    boxes.append({
                        "type": m[0].strip(),
                        "x": int(m[1]) / 10, "y": int(m[2]) / 10,
                        "w": (int(m[3]) - int(m[1])) / 10, "h": (int(m[4]) - int(m[2])) / 10
                    })
                except: continue

            # 清洗 Markdown 文本
            # 移除 [Type, x1, y1, x2, y2]
            clean_markdown = re.sub(r"\[[a-zA-Z]+,\s*\d+,\s*\d+,\s*\d+,\s*\d+\]", "", full_text)
            # 移除 <|ref|>...<|/det|>
            clean_markdown = re.sub(r"<\|ref\|>.*?<\|/ref\|><\|det\|>\[\[.*?\]\]<\|/det\|>", "", clean_markdown).strip()

            return {
                "structured_data": boxes, 
                "markdown": clean_markdown
            }
        except Exception as e:
            print(f"[-] OCR to Markdown Error: {e}")
            return {"structured_data": [], "markdown": "解析失败"}

    def process_pdf_pages(self, images):
        from concurrent.futures import ThreadPoolExecutor
        num_pages = len(images)
        
        def process_single_page(args):
            idx, img = args
            res = self.process_image(img)
            return idx, res

        all_pages_data = []
        with ThreadPoolExecutor(max_workers=min(num_pages, 8)) as executor:
            task_args = [(i, img) for i, img in enumerate(images)]
            map_results = list(executor.map(process_single_page, task_args))

            for idx, page_result in map_results:
                all_pages_data.append({
                    "page": idx + 1,
                    "markdown": page_result["markdown"],
                    "boxes": page_result["structured_data"]
                })

        return sorted(all_pages_data, key=lambda x: x["page"])
