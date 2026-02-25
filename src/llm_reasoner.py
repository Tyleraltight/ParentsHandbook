from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception


def _is_retriable(exc: BaseException) -> bool:
    """Only retry on 503 Service Unavailable or generic server errors."""
    exc_str = str(exc).lower()
    if "503" in exc_str or "unavailable" in exc_str or "capacity" in exc_str:
        return True
    if "500" in exc_str or "internal" in exc_str:
        return True
    return False
from src.config import settings

# -------------------------------------------------------------
# Data Models for Structured Output
# -------------------------------------------------------------
class DimensionScore(BaseModel):
    level: str = Field(description="Must be exactly one of: None, Mild, Moderate, Severe.")
    score: int = Field(description="Numeric score from 0 to 10 rating the intensity.")
    summary: str = Field(description="A brief summary of this specific dimension. MUST be in Simplified Chinese.")
    original_quotes: List[str] = Field(description="List of exact quotes from the raw english text supporting this score and level.")
    confidence_score: float = Field(description="Float from 0.0 to 1.0 representing your confidence in this assessment.")

class OverallAnalysis(BaseModel):
    analysis: str = Field(description="Detailed overall analysis of all the parental guide dimensions. MUST be in Simplified Chinese.")
    conclusion: str = Field(description="Final brief conclusion or recommendation for parents. MUST be in Simplified Chinese.")
    context_tags: List[str] = Field(description="Short structural tags for UI, e.g., '血腥镜头', '脏话较多', '适合全家'. MUST be in Simplified Chinese.")

class ParentalGuideReport(BaseModel):
    sex_and_nudity: DimensionScore
    violence_and_gore: DimensionScore
    profanity: DimensionScore
    frightening_scenes: DimensionScore
    overall: OverallAnalysis

class AllDimensionsResult(BaseModel):
    sex_and_nudity: DimensionScore
    violence_and_gore: DimensionScore
    profanity: DimensionScore
    frightening_scenes: DimensionScore

# -------------------------------------------------------------
# Reasoner Logic
# -------------------------------------------------------------
class LLMReasoner:
    def __init__(self):
        self.client = genai.Client(
            api_key=settings.google_api_key,
            http_options={"timeout": 120_000},  # 120s for streaming
        )
        self.fast_model = settings.base_parsing_model
        self.pro_model = settings.analysis_model

    @retry(wait=wait_exponential(multiplier=2, min=2, max=30), stop=stop_after_attempt(5), retry=retry_if_exception(_is_retriable))
    def _generate_all_dimensions_content(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.fast_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AllDimensionsResult,
                temperature=0.1, # Low temperature for analytical consistency
            ),
        )
        return response.text

    async def _async_generate_all_dimensions_content(self, prompt: str) -> str:
        """Async LLM call using google-genai aio interface."""
        response = await self.client.aio.models.generate_content(
            model=self.fast_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AllDimensionsResult,
                temperature=0.1,
            ),
        )
        return response.text

    def parse_all_dimensions(self, all_raw_texts: Dict[str, str]) -> dict:
        """
        Uses the faster flash model to extract specific structured data for ALL dimensions in one single call.
        """
        prompt = f"""
        You are an expert film content analyst. I will provide you with the raw HTML/text from IMDb's Parental Guide for multiple dimensions.
        
        Analyze the texts and provide a structured JSON response containing the evaluations for ALL dimensions.
        
        CRITICAL INSTRUCTIONS:
        1. Read the text for each dimension carefully and determine its `level` and a `score` (0-10).
        2. Provide exactly matching `original_quotes` from the raw text that justify your score. Keep quotes precise.
        3. Write the `summary` in **Simplified Chinese (简体中文)** ONLY.
        4. If the provided text for any dimension is shorter than 10 characters or effectively missing/meaningless (like 'None'), force its `level` to "Unknown", `score` to 0, `summary` to "Data Missing (数据缺失)", and leave `original_quotes` empty without guessing.
        
        RAW TEXTS MAPPING:
        {all_raw_texts}
        """

        try:
            response_text = self._generate_all_dimensions_content(prompt)
            return AllDimensionsResult.model_validate_json(response_text).model_dump()
        except Exception as e:
            # Fallback or empty struct in case of complete block failure
            fallback_dim = DimensionScore(
                level="Unknown", score=0, summary=f"提取失败或分析超时: {str(e)}", 
                original_quotes=[], confidence_score=0.0
            ).model_dump()
            return {
                "sex_and_nudity": fallback_dim,
                "violence_and_gore": fallback_dim,
                "profanity": fallback_dim,
                "frightening_scenes": fallback_dim
            }

    @retry(wait=wait_exponential(multiplier=2, min=2, max=30), stop=stop_after_attempt(5), retry=retry_if_exception(_is_retriable))
    def _generate_overall_content(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.fast_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=OverallAnalysis,
                temperature=0.1,
            ),
        )
        return response.text

    async def _async_generate_overall_content(self, prompt: str) -> str:
        """Async LLM call for overall analysis."""
        response = await self.client.aio.models.generate_content(
            model=self.fast_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=OverallAnalysis,
                temperature=0.1,
            ),
        )
        return response.text

    def generate_overall_analysis(self, dimensions_data: Dict[str, Any]) -> dict:
        """
        Uses the pro model to look at all dimensions and write a deep overall analysis.
        """
        prompt = f"""
        You are an expert parental guide evaluator. Below are the summarized dimension scores and quotes for a movie.
        
        {dimensions_data}
        
        Please provide a detailed overall analysis, a final conclusion, and context tags.
        
        CRITICAL INSTRUCTIONS:
        1. ALL OUTPUT STRINGS (analysis, conclusion, context_tags) MUST BE IN **Simplified Chinese (简体中文)**.
        2. `context_tags` should be 3-5 short phrases suitable for UI badges (e.g., "重度暴力", "轻微粗口", "裸露镜头").
        """

        try:
            response_text = self._generate_overall_content(prompt)
            return OverallAnalysis.model_validate_json(response_text).model_dump()
        except Exception as e:
            return OverallAnalysis(
                analysis="分析超时或失败", conclusion=f"大模型返回异常: {str(e)}", context_tags=["系统超时"]
            ).model_dump()

    async def async_parse_all_dimensions(self, all_raw_texts: Dict[str, str]) -> dict:
        """Async batch version (non-streaming fallback)."""
        prompt = self._build_dims_prompt(all_raw_texts)
        try:
            response_text = await self._async_generate_all_dimensions_content(prompt)
            return AllDimensionsResult.model_validate_json(response_text).model_dump()
        except Exception as e:
            return self._fallback_dims(str(e))

    async def async_stream_dimensions(self, all_raw_texts: Dict[str, str]):
        """
        Async generator: tries streaming first, falls back to batch.
        Either way, yields (dim_key, result_dict) one by one.
        """
        import json
        prompt = self._build_dims_prompt(all_raw_texts)
        dim_keys = ["sex_and_nudity", "violence_and_gore", "profanity", "frightening_scenes"]
        emitted = set()

        # --- Attempt 1: streaming ---
        try:
            response = await self.client.aio.models.generate_content_stream(
                model=self.fast_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AllDimensionsResult,
                    temperature=0.1,
                ),
            )
            buffer = ""
            async for chunk in response:
                if chunk.text:
                    buffer += chunk.text
                for key in dim_keys:
                    if key in emitted:
                        continue
                    obj = self._try_extract_dim(buffer, key)
                    if obj is not None:
                        emitted.add(key)
                        try:
                            result = DimensionScore.model_validate(obj).model_dump()
                        except Exception:
                            result = obj
                        yield (key, result)

            # Emit any remaining after stream ends
            if len(emitted) < 4 and buffer:
                try:
                    full = json.loads(buffer)
                    for key in dim_keys:
                        if key not in emitted:
                            if key in full:
                                emitted.add(key)
                                yield (key, DimensionScore.model_validate(full[key]).model_dump())
                except Exception:
                    pass

        except Exception as e:
            print(f"[LLM] Streaming failed ({type(e).__name__}), falling back to batch...")

        # --- Attempt 2: batch fallback for any missing dims ---
        if len(emitted) < 4:
            try:
                print("[LLM] Using batch generate_content fallback...")
                resp = await self.client.aio.models.generate_content(
                    model=self.fast_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=AllDimensionsResult,
                        temperature=0.1,
                    ),
                )
                full = json.loads(resp.text)
                for key in dim_keys:
                    if key not in emitted:
                        emitted.add(key)
                        try:
                            yield (key, DimensionScore.model_validate(full[key]).model_dump())
                        except Exception:
                            yield (key, full.get(key, self._fallback_dim("Parse error")))
            except Exception as e2:
                print(f"[LLM] Batch fallback also failed: {type(e2).__name__}: {e2}")
                for key in dim_keys:
                    if key not in emitted:
                        yield (key, self._fallback_dim(str(e2)))

    @staticmethod
    def _try_extract_dim(buffer: str, dim_key: str):
        """Extract a complete dimension object from partial JSON using brace counting."""
        import json
        marker = f'"{dim_key}"'
        idx = buffer.find(marker)
        if idx == -1:
            return None

        # Find the colon after the key
        colon_idx = buffer.find(':', idx + len(marker))
        if colon_idx == -1:
            return None

        # Find the opening brace of the value object
        brace_start = buffer.find('{', colon_idx)
        if brace_start == -1:
            return None

        # Count braces, respecting strings
        depth = 0
        in_string = False
        escape_next = False
        for i in range(brace_start, len(buffer)):
            ch = buffer[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    obj_str = buffer[brace_start:i + 1]
                    try:
                        return json.loads(obj_str)
                    except json.JSONDecodeError:
                        return None
        return None  # Object not yet complete

    @staticmethod
    def _build_dims_prompt(all_raw_texts: Dict[str, str]) -> str:
        return f"""You are an expert film content analyst. Analyze the raw text from IMDb's Parental Guide.

Output a pure JSON object with exactly these four keys in order:
sex_and_nudity, violence_and_gore, profanity, frightening_scenes.

RULES:
1. Each dimension needs: level (None/Mild/Moderate/Severe), score (0-10), summary (简体中文), original_quotes (English list), confidence_score (0.0-1.0).
2. If text < 10 chars or meaningless, force level="Unknown", score=0, summary="数据缺失", original_quotes=[].
3. NO markdown, NO explanation, ONLY the JSON object.

RAW TEXTS:
{all_raw_texts}"""

    @staticmethod
    def _fallback_dim(reason: str) -> dict:
        return DimensionScore(
            level="Unknown", score=0, summary=f"分析失败: {reason}",
            original_quotes=[], confidence_score=0.0
        ).model_dump()

    @staticmethod
    def _fallback_dims(reason: str) -> dict:
        d = LLMReasoner._fallback_dim(reason)
        return {
            "sex_and_nudity": d, "violence_and_gore": d,
            "profanity": d, "frightening_scenes": d
        }

    async def async_parse_single_dimension(self, dim_key: str, dim_label: str, raw_text: str) -> tuple:
        """Analyze a single dimension independently. Returns (dim_key, result_dict)."""
        prompt = f"""You are an expert film content analyst. Analyze the following raw text from IMDb's Parental Guide for the "{dim_label}" dimension.

CRITICAL INSTRUCTIONS:
1. Determine the `level` (exactly one of: None, Mild, Moderate, Severe) and a `score` (0-10).
2. Provide exactly matching `original_quotes` from the raw text that justify your score.
3. Write the `summary` in **Simplified Chinese (简体中文)** ONLY.
4. If the text is shorter than 10 characters or meaningless, force `level` to "Unknown", `score` to 0, `summary` to "数据缺失", and leave `original_quotes` empty.

RAW TEXT:
{raw_text}"""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.fast_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DimensionScore,
                    temperature=0.1,
                ),
            )
            result = DimensionScore.model_validate_json(response.text).model_dump()
        except Exception as e:
            result = DimensionScore(
                level="Unknown", score=0, summary=f"分析失败: {str(e)}",
                original_quotes=[], confidence_score=0.0
            ).model_dump()
        return (dim_key, result)

    async def async_generate_overall_analysis(self, dimensions_data: Dict[str, Any]) -> dict:
        """Async version of generate_overall_analysis."""
        prompt = f"""
        You are an expert parental guide evaluator. Below are the summarized dimension scores and quotes for a movie.
        
        {dimensions_data}
        
        Please provide a detailed overall analysis, a final conclusion, and context tags.
        
        CRITICAL INSTRUCTIONS:
        1. ALL OUTPUT STRINGS (analysis, conclusion, context_tags) MUST BE IN **Simplified Chinese (简体中文)**.
        2. `context_tags` should be 3-5 short phrases suitable for UI badges (e.g., "重度暴力", "轻微粗口", "裸露镜头").
        """
        try:
            response_text = await self._async_generate_overall_content(prompt)
            return OverallAnalysis.model_validate_json(response_text).model_dump()
        except Exception as e:
            return OverallAnalysis(
                analysis="分析超时或失败", conclusion=f"大模型返回异常: {str(e)}", context_tags=["系统超时"]
            ).model_dump()
