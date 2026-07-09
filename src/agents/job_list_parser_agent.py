"""Job list parser for CSV, Excel, and pasted multi-JD text."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

from src.agents.jd_parser_agent import JDParserAgent
from src.llm_client import LLMClient
from src.schemas.models import JobPosting
from src.utils.text_utils import normalize_text


class JobListParserAgent:
    """Normalize heterogeneous job-list inputs without failing the whole batch."""

    COLUMN_ALIASES = {
        "job_title": ("job_title", "岗位名称", "职位名称", "岗位", "职位"),
        "company": ("company", "公司", "企业"),
        "city": ("city", "城市", "地点", "工作地点"),
        "job_type": ("job_type", "岗位类型", "职位类型"),
        "jd_text": ("jd_text", "jd", "岗位描述", "职位描述", "岗位jd"),
        "source_url": ("source_url", "url", "来源链接", "岗位链接"),
        "publish_date": ("publish_date", "发布日期", "发布时间"),
    }

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm = llm_client or LLMClient()
        self.jd_parser = JDParserAgent(self.llm)

    def run(
        self,
        *,
        file_name: str = "",
        content: bytes = b"",
        multi_jd_text: str = "",
    ) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        if file_name and content:
            jobs.extend(self.parse_file(file_name, content))
        if normalize_text(multi_jd_text):
            jobs.extend(self.parse_multi_jd_text(multi_jd_text))

        return [
            job.model_copy(update={"job_id": f"job-{index:03d}"})
            for index, job in enumerate(jobs, start=1)
        ]

    def parse_file(self, file_name: str, content: bytes) -> List[JobPosting]:
        suffix = Path(file_name).suffix.lower()
        if suffix == ".csv":
            dataframe = self._read_csv(content)
        elif suffix in {".xlsx", ".xls"}:
            try:
                dataframe = pd.read_excel(io.BytesIO(content))
            except ImportError as exc:
                raise ValueError("Excel 解析需要 openpyxl，请先安装 requirements.txt。") from exc
            except Exception as exc:
                raise ValueError(f"无法读取 Excel 岗位列表：{exc}") from exc
        else:
            raise ValueError("不支持的岗位列表格式，请上传 .csv、.xlsx 或 .xls 文件。")
        return self.parse_dataframe(dataframe)

    def parse_dataframe(self, dataframe: pd.DataFrame) -> List[JobPosting]:
        if dataframe.empty:
            return []

        columns = {str(column).strip().lower(): column for column in dataframe.columns}
        jobs: List[JobPosting] = []
        for row_index, (_, row) in enumerate(dataframe.iterrows(), start=1):
            values = {
                field: self._row_value(row, columns, aliases)
                for field, aliases in self.COLUMN_ALIASES.items()
            }
            jd_text = normalize_text(values["jd_text"])
            if not jd_text:
                continue
            jobs.append(
                JobPosting(
                    job_id=f"job-{row_index:03d}",
                    job_title=values["job_title"] or "未知岗位",
                    company=values["company"] or "公司未知",
                    city=values["city"] or "城市未知",
                    job_type=values["job_type"] or "岗位类型未知",
                    jd_text=jd_text,
                    source_url=values["source_url"],
                    publish_date=values["publish_date"],
                )
            )
        return jobs

    def parse_multi_jd_text(self, text: str) -> List[JobPosting]:
        blocks = [normalize_text(block) for block in re.split(r"\s*---JOB---\s*", text)]
        jobs: List[JobPosting] = []
        for index, block in enumerate((item for item in blocks if item), start=1):
            analysis = self.jd_parser.run(block)
            jobs.append(
                JobPosting(
                    job_id=f"job-{index:03d}",
                    job_title=analysis.job_title or "未知岗位",
                    company=analysis.company or "公司未知",
                    city=analysis.location or "城市未知",
                    job_type=self._extract_job_type(block),
                    jd_text=block,
                    source_url=self._extract_url(block),
                    publish_date=self._extract_publish_date(block),
                )
            )
        return jobs

    def _read_csv(self, content: bytes) -> pd.DataFrame:
        last_error: Optional[Exception] = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return pd.read_csv(io.BytesIO(content), encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
            except Exception as exc:
                raise ValueError(f"无法读取 CSV 岗位列表：{exc}") from exc
        raise ValueError(f"无法识别 CSV 文件编码：{last_error}")

    def _row_value(self, row: pd.Series, columns: dict[str, Any], aliases: tuple[str, ...]) -> str:
        for alias in aliases:
            source_column = columns.get(alias.lower())
            if source_column is None:
                continue
            value = row[source_column]
            if pd.isna(value):
                return ""
            if isinstance(value, pd.Timestamp):
                return value.strftime("%Y-%m-%d")
            return str(value).strip()
        return ""

    def _extract_job_type(self, text: str) -> str:
        match = re.search(r"(?:岗位类型|职位类型|类型)\s*[:：]\s*([^\n]+)", text)
        if match:
            return match.group(1).strip()
        for label in ("可转正实习", "实习", "校招", "全职"):
            if label in text:
                return label
        return "岗位类型未知"

    def _extract_url(self, text: str) -> str:
        match = re.search(r"https?://[^\s)）]+", text)
        return match.group(0).rstrip(".,，。") if match else ""

    def _extract_publish_date(self, text: str) -> str:
        match = re.search(
            r"(?:发布日期|发布时间)\s*[:：]\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)",
            text,
        )
        return match.group(1) if match else ""
