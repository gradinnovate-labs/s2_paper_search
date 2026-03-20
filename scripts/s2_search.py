#!/usr/bin/env python3
"""
S2 Paper Search - Semantic Scholar 論文搜尋工具

通用型論文搜尋工具，支援自訂搜尋條件、主題過濾和會議過濾。
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class S2APIError(Exception):
    """Semantic Scholar API 錯誤"""
    pass


class S2APIClient:
    """Semantic Scholar API 客戶端"""
    
    def __init__(self, api_key: str | None = None):
        self.base_url = "https://api.semanticscholar.org/graph/v1"
        self.headers = {"x-api-key": api_key} if api_key else {}
        self.use_bulk_search = True
    
    def search_papers(
        self,
        query: str,
        year_range: str | None = None,
        venues: List[str] | None = None,
        fields: List[str] | None = None,
        limit: int = 100,
        batch_size: int = 100,
        delay: float = 1.0,
        max_retries: int = 3
    ):
        """搜尋論文"""
        default_fields = ["title", "abstract", "authors", "venue", "year", "url", "publicationDate", "paperId"]
        
        params = {
            "query": query,
            "fields": ",".join(fields or default_fields),
            "limit": str(min(limit, batch_size)),
        }
        
        if year_range:
            params["year"] = year_range
        if venues:
            params["venue"] = ",".join(venues)
        
        token = None
        total_count = 0
        
        while total_count < limit:
            if token:
                params["token"] = token
            
            response = self._make_request("/paper/search/bulk", params, delay, max_retries)
            
            if response.get("data"):
                batch = response["data"]
                batch_count = len(batch)
                total_count += batch_count
                logger.info(f"取得 {batch_count} 篇論文 (累計: {total_count})")
                yield batch
            
            token = response.get("token")
            if not token or total_count >= limit:
                break
    
    def _make_request(self, endpoint: str, params: dict, delay: float, max_retries: int) -> dict:
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 403:
                    if endpoint == "/paper/search/bulk" and self.use_bulk_search:
                        logger.warning("Bulk search 被拒絕，改用 regular search")
                        self.use_bulk_search = False
                        endpoint = "/paper/search"
                        continue
                    raise S2APIError(f"存取被拒絕 (403)")
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"請求頻率限制，等待 {retry_after} 秒...")
                    import time
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(delay * (attempt + 1))
                else:
                    raise S2APIError(f"請求失敗: {e}")
        
        raise S2APIError("請求處理發生錯誤")


class PaperFilter:
    """論文過濾器"""
    
    def __init__(
        self,
        topic_keywords: Dict[str, List[str]] | None = None,
        venue_patterns: Dict[str, List[str]] | None = None
    ):
        self.topic_keywords = topic_keywords or {}
        self.venue_patterns = venue_patterns or {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        import re
        self.topic_compiled = {}
        for topic, keywords in self.topic_keywords.items():
            self.topic_compiled[topic] = [
                re.compile(kw, re.IGNORECASE) for kw in keywords
            ]
        
        self.venue_compiled = {}
        for venue, patterns in self.venue_patterns.items():
            self.venue_compiled[venue] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def match_topic(self, title: str, abstract: str) -> tuple[bool, List[str]]:
        if not self.topic_compiled:
            return True, []
        
        text = f"{title} {abstract or ''}".lower()
        matched = []
        
        for topic, patterns in self.topic_compiled.items():
            if any(p.search(text) for p in patterns):
                matched.append(topic)
        
        return len(matched) > 0, matched
    
    def is_target_venue(self, venue: str) -> bool:
        if not self.venue_compiled:
            return True
        
        if not venue:
            return False
        
        venue_lower = venue.lower()
        for patterns in self.venue_compiled.values():
            if any(p.search(venue_lower) for p in patterns):
                return True
        return False
    
    def normalize_venue(self, venue: str) -> str:
        if not venue or not self.venue_compiled:
            return venue or "Unknown"
        
        venue_lower = venue.lower()
        for venue_name, patterns in self.venue_compiled.items():
            if any(p.search(venue_lower) for p in patterns):
                return venue_name
        return venue


class CSVExporter:
    """CSV 匯出器"""
    
    def __init__(self, output_path: str, fieldnames: List[str] | None = None):
        self.output_path = output_path
        self.fieldnames = fieldnames or ["標題", "摘要", "連結", "作者", "日期", "會議", "主題"]
        self.papers: List[dict] = []
        self.seen_ids: set = set()
    
    @property
    def count(self) -> int:
        return len(self.papers)
    
    def add_paper(self, paper_data: dict, paper_id: str | None = None) -> bool:
        if paper_id and paper_id in self.seen_ids:
            return False
        if paper_id:
            self.seen_ids.add(paper_id)
        self.papers.append(paper_data)
        return True
    
    def export(self):
        import csv
        if not self.papers:
            logger.warning("沒有論文可匯出")
            return
        
        with open(self.output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()
            writer.writerows(self.papers)
        
        logger.info(f"已匯出 {self.count} 篇論文至 {self.output_path}")


def load_config(config_path: str) -> dict:
    """載入 JSON 配置檔"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_args():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(
        description='Semantic Scholar 論文搜尋工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 使用命令列參數
  python s2_search.py -q "reinforcement learning" -y 2024-2026 -o papers.csv
  
  # 使用配置檔
  python s2_search.py -c config.json
  
  # 指定會議和主題
  python s2_search.py -q "machine learning" --venues NeurIPS ICML --topics RL DT
        """
    )
    
    parser.add_argument('-c', '--config', help='配置檔路徑 (JSON)')
    parser.add_argument('-q', '--query', nargs='+', help='搜尋查詢 (可多個)')
    parser.add_argument('-y', '--year', help='年份範圍 (如: 2024-2026)')
    parser.add_argument('--venues', nargs='+', help='目標會議 (可多個)')
    parser.add_argument('-t', '--topics', nargs='+', help='目標主題 (可多個)')
    parser.add_argument('-o', '--output', default='paper_list.csv', help='輸出檔案路徑')
    parser.add_argument('-l', '--limit', type=int, default=10000, help='最大搜尋數量')
    parser.add_argument('--api-key', help='Semantic Scholar API Key (可選)')
    parser.add_argument('--topic-file', help='主題關鍵詞配置檔 (JSON)')
    parser.add_argument('--venue-file', help='會議匹配配置檔 (JSON)')
    parser.add_argument('--verbose', action='store_true', help='顯示詳細輸出')
    
    return parser.parse_args()


def build_topic_keywords(topics: List[str] | None, topic_file: str | None) -> Dict[str, List[str]]:
    """建立主題關鍵詞"""
    default_topics = {
        "RL": ["reinforcement\\s+learning", "deep\\s+reinforcement\\s+learning", "policy\\s+gradient", "actor\\s*-?\\s*critic", "q-?learning"],
        "DT": ["decision\\s+transformer", "trajectory\\s+transformer"],
        "ICRL": ["in-?context\\s+reinforcement\\s+learning", "few-?shot\\s+reinforcement\\s+learning"]
    }
    
    if topic_file:
        with open(topic_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    if topics:
        return {t: default_topics.get(t, []) for t in topics if t in default_topics}
    
    return default_topics


def build_venue_patterns(venues: List[str] | None, venue_file: str | None) -> Dict[str, List[str]]:
    """建立會議匹配模式"""
    default_venues = {
        "AAAI": ["aaai"],
        "IJCAI": ["ijcai"],
        "NeurIPS": ["neurips", "neural\\s+information\\s+processing\\s+systems"],
        "ICML": ["icml", "international\\s+conference\\s+on\\s+machine\\s+learning"],
        "ICLR": ["iclr", "international\\s+conference\\s+on\\s+learning\\s+representations"],
        "KDD": ["kdd", "knowledge\\s+discovery\\s+and\\s+data\\s+mining"]
    }
    
    if venue_file:
        with open(venue_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    if venues:
        return {v: default_venues.get(v, [v.lower()]) for v in venues}
    
    return default_venues


def main():
    args = parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 載入配置
    if args.config:
        config = load_config(args.config)
        queries = config.get('queries', [])
        year_range = config.get('year_range')
        venues = config.get('venues')
        topics = config.get('topics')
        output = config.get('output', 'paper_list.csv')
        limit = config.get('limit', 10000)
        api_key = config.get('api_key') or os.getenv('S2_API_KEY')
    else:
        queries = args.query or []
        year_range = args.year
        venues = args.venues
        topics = args.topics
        output = args.output
        limit = args.limit
        api_key = args.api_key or os.getenv('S2_API_KEY')
    
    if not queries:
        logger.error("請提供搜尋查詢 (-q) 或配置檔 (-c)")
        sys.exit(1)
    
    logger.info(f"開始搜尋論文...")
    logger.info(f"查詢: {queries}")
    logger.info(f"年份: {year_range or '不限'}")
    logger.info(f"會議: {venues or '不限'}")
    
    # 初始化組件
    client = S2APIClient(api_key)
    topic_keywords = build_topic_keywords(topics, args.topic_file)
    venue_patterns = build_venue_patterns(venues, args.venue_file)
    paper_filter = PaperFilter(topic_keywords, venue_patterns)
    exporter = CSVExporter(output)
    
    total_searched = 0
    total_matched = 0
    
    for query in queries:
        logger.info(f"搜尋: {query}")
        query_count = 0
        query_matched = 0
        
        try:
            for batch in client.search_papers(
                query=query,
                year_range=year_range,
                limit=limit
            ):
                for paper in batch:
                    query_count += 1
                    total_searched += 1
                    
                    title = paper.get("title", "")
                    abstract = paper.get("abstract", "")
                    venue = paper.get("venue", "")
                    
                    # 過濾會議
                    if not paper_filter.is_target_venue(venue):
                        continue
                    
                    # 過濾主題
                    is_match, matched_topics = paper_filter.match_topic(title, abstract)
                    if not is_match:
                        continue
                    
                    # 匯出
                    authors = ", ".join([a.get("name", "") for a in paper.get("authors", [])])
                    paper_data = {
                        "標題": title,
                        "摘要": abstract,
                        "連結": paper.get("url", ""),
                        "作者": authors,
                        "日期": paper.get("publicationDate") or str(paper.get("year", "")),
                        "會議": paper_filter.normalize_venue(venue),
                        "主題": ", ".join(matched_topics)
                    }
                    
                    if exporter.add_paper(paper_data, paper.get("paperId")):
                        query_matched += 1
                        total_matched += 1
        
        except Exception as e:
            logger.error(f"搜尋 '{query}' 錯誤: {e}")
        
        logger.info(f"查詢 '{query}': 搜尋 {query_count} 篇，符合 {query_matched} 篇")
    
    exporter.export()
    logger.info(f"✓ 完成！共搜尋 {total_searched} 篇，匯出 {total_matched} 篇")


if __name__ == "__main__":
    main()
