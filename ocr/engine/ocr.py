import os
import base64
import httpx
import re
import time
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# 优化：预编译正则表达式以提升性能
GROUNDING_PATTERN = re.compile(
    r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>",
    re.DOTALL
)
CLEAN_GROUNDING_PATTERN = re.compile(
    r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[.*?\]\]<\|/det\|>",
    re.DOTALL
)
OLD_COORD_PATTERN = re.compile(r"\[([a-zA-Z]+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]")
CLEAN_OLD_COORD_PATTERN = re.compile(r"\[[a-zA-Z]+,\s*\d+,\s*\d+,\s*\d+,\s*\d+\]")

class OCREngine:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.model_id = os.getenv("OCR_MODEL_ID", "deepseek-ai/DeepSeek-OCR")
        self.max_workers = int(os.getenv("OCR_MAX_WORKERS", "4"))
        self.http_timeout_sec = float(os.getenv("OCR_HTTP_TIMEOUT_SEC", "180"))
        # 优化：使用连接池提升并发性能
        self._client = httpx.Client(
            timeout=httpx.Timeout(self.http_timeout_sec),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )

    def _encode_image(self, image, max_size=1500, jpeg_quality=80):
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 优化：限制图片最大尺寸，减少传输和模型处理压力
        if max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)
            
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=jpeg_quality, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_vlm_api(self, payload):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        response = self._client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def process_image(self, image, max_size=1600, jpeg_quality=75):
        """
        利用多模态模型将图片全量转化为带坐标的格式。
        优化：降低默认图片质量以加速编码和传输
        """
        base64_image = self._encode_image(image, max_size=max_size, jpeg_quality=jpeg_quality)
        
        # 优化 Prompt：要求模型使用 interleaved (交织) 格式，这样文字和坐标才能 100% 匹配
        prompt_text = """你现在的身份是一个高精度【视觉文档分析师】。请对图片进行全要素识别。

对于页面中的每个逻辑块（段落、标题、表格、图片等），请按以下格式顺序输出：
<|ref|>文本内容或要素描述<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>

要求：
1. 如果是文本段落，<|ref|>内为原始文本内容。
2. 如果是表格，<|ref|>内为完整的 Markdown 表格代码。
3. 如果是图片/图表，<|ref|>内为对该图内容的简要描述。
4. 坐标使用 0-1000 归一化坐标系。
5. 保持原始语言，严禁总结。直接开始输出内容。"""

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

            # 1. 提取所有带坐标的块 - 优化：使用预编译的正则表达式
            boxes = []
            grounding_patterns = GROUNDING_PATTERN.findall(full_text)
            
            for m in grounding_patterns:
                try:
                    text_content = m[0].strip()
                    x1, y1, x2, y2 = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                    
                    # 增强类型识别逻辑
                    inferred_type = "文本"
                    lowered_text = text_content.lower()
                    if "|" in text_content and "---" in text_content:
                        inferred_type = "表格"
                    elif any(k in lowered_text for k in ["figure", "diagram", "chart", "流程图", "架构图", "时序图", "拓扑图", "示意图", "统计图"]):
                        inferred_type = "图表"
                    elif re.search(r"^(图|fig|figure)\s*\d+", lowered_text):
                        inferred_type = "图表"
                    elif "|" in text_content:
                        inferred_type = "表格"

                    boxes.append({
                        "text": text_content,
                        "x": x1 / 10, "y": y1 / 10,
                        "w": (x2 - x1) / 10, "h": (y2 - y1) / 10,
                        "type": inferred_type
                    })
                except: continue

            # 2. 生成纯净的 Markdown 供 UI 显示 - 优化：使用预编译的正则表达式
            clean_markdown = CLEAN_GROUNDING_PATTERN.sub(r"\1", full_text).strip()

            # 3. 兼容老格式（防止模型没按新要求输出）- 优化：使用预编译的正则表达式
            if not boxes:
                type_map = {
                    "Text": "文本",
                    "Table": "表格",
                    "Figure": "图表",
                    "Chart": "图表",
                    "Equation": "公式",
                    "Header": "标题",
                    "Footer": "页脚"
                }
                coord_patterns = OLD_COORD_PATTERN.findall(full_text)
                for m in coord_patterns:
                    try:
                        raw_type = m[0].strip()
                        boxes.append({
                            "type": type_map.get(raw_type, raw_type),
                            "x": int(m[1]) / 10, "y": int(m[2]) / 10,
                            "w": (int(m[3]) - int(m[1])) / 10, "h": (int(m[4]) - int(m[2])) / 10
                        })
                    except: continue
                clean_markdown = CLEAN_OLD_COORD_PATTERN.sub("", full_text).strip()

            return {
                "structured_data": boxes, 
                "markdown": clean_markdown,
                "grounded_markdown": full_text
            }
        except Exception as e:
            print(f"[-] OCR to Markdown Error: {e}")
            return {"structured_data": [], "markdown": "解析失败", "grounded_markdown": "解析失败"}

    def _process_image_with_fallback(self, image):
        # 优化：调整降采样策略，更快的初始尝试
        attempt_profiles = [
            (1600, 75),  # 优化：从 2000/85 降低
            (1400, 70),  # 优化：从 1600/80 降低
            (1200, 65),  # 优化：从 1200/75 降低
        ]
        last_result = {"structured_data": [], "markdown": "解析失败", "grounded_markdown": "解析失败"}
        for idx, (max_size, quality) in enumerate(attempt_profiles, start=1):
            result = self.process_image(image, max_size=max_size, jpeg_quality=quality)
            if result.get("markdown") and result["markdown"] != "解析失败":
                if idx > 1:
                    print(f"[+] OCR fallback succeeded on attempt {idx} (max_size={max_size}, q={quality})")
                return result
            last_result = result
            time.sleep(0.4 * idx)
        return last_result

    def process_pdf_pages(self, images, callback=None):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        
        num_pages = len(images)
        if num_pages == 0:
            return []
            
        finished_pages = 0
        progress_lock = threading.Lock()
        
        def process_single_page(args):
            nonlocal finished_pages
            idx, img = args
            res = self._process_image_with_fallback(img)
            
            with progress_lock:
                finished_pages += 1
                if callback:
                    callback(finished_pages, num_pages)
            return idx, res

        all_pages_data = []
        worker_count = max(1, min(num_pages, self.max_workers))
        print(f"[*] OCR worker count: {worker_count}, timeout={self.http_timeout_sec}s")
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            task_args = [(i, img) for i, img in enumerate(images)]
            map_results = list(executor.map(process_single_page, task_args))

            for idx, page_result in map_results:
                all_pages_data.append({
                    "page": idx + 1,
                    "markdown": page_result["markdown"],
                    "boxes": page_result["structured_data"],
                    "grounded_markdown": page_result.get("grounded_markdown", page_result["markdown"])
                })

        # 对失败页进行一次串行补偿重跑，进一步降低批量超时带来的失败概率
        failed_pages = [p for p in all_pages_data if p.get("markdown") == "解析失败"]
        if failed_pages:
            print(f"[!] Retry failed OCR pages sequentially: {len(failed_pages)}")
            for failed in failed_pages:
                page_idx = failed["page"] - 1
                if 0 <= page_idx < len(images):
                    retry_res = self._process_image_with_fallback(images[page_idx])
                    failed["markdown"] = retry_res.get("markdown", "解析失败")
                    failed["boxes"] = retry_res.get("structured_data", [])
                    failed["grounded_markdown"] = retry_res.get("grounded_markdown", "解析失败")

        return sorted(all_pages_data, key=lambda x: x["page"])
