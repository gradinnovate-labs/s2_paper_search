---
name: s2 paper search
description: Semantic Scholar 論文搜尋工具，用於搜尋學術論文並匯出為 CSV。
---
# S2 Paper Search Skill

Semantic Scholar 論文搜尋工具，用於搜尋學術論文並匯出為 CSV。

## 觸發條件

當用戶需要以下任務時使用此技能：
- 搜尋特定主題的學術論文
- 查找特定會議或期刊的論文
- 搜尋特定年份範圍的論文
- 匯出論文清單為 CSV 格式
- 進行文獻調研

關鍵詞：論文搜尋、paper search、文獻調研、Semantic Scholar、學術論文

## 使用方式

### 基本命令

```bash
python scripts/s2_search.py [選項]
```

### 必要參數

必須提供以下其中一種：
- `-q, --query`: 搜尋查詢詞
- `-c, --config`: JSON 配置檔路徑

### 可選參數

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `-y, --year` | 年份範圍 (如 2024-2026) | 不限 |
| `--venues` | 目標會議/期刊 | 不限 |
| `-t, --topics` | 目標主題 | 不限 |
| `-o, --output` | 輸出 CSV 檔案 | paper_list.csv |
| `-l, --limit` | 最大搜尋數量 | 10000 |
| `--api-key` | S2 API Key | 從環境變數讀取 |
| `--topic-file` | 主題關鍵詞配置檔 | 內建 AI 主題 |
| `--venue-file` | 會議匹配配置檔 | 內建 AI 會議 |
| `--verbose` | 顯示詳細輸出 | 否 |

## 領域配置

### AI/ML 領域

```bash
# 使用 AI 配置
python scripts/s2_search.py -c assets/config_ai.example.json

# 搜尋強化學習論文
python scripts/s2_search.py \
  -q "reinforcement learning" "decision transformer" \
  -y 2024-2026 \
  --venues NeurIPS ICML ICLR AAAI \
  --topics RL DT ICRL \
  -o ai_rl_papers.csv
```

### EDA/VLSI 領域

```bash
# 使用 EDA 配置
python scripts/s2_search.py -c assets/config_eda.example.json

# 搜尋 Physical Design 論文
python scripts/s2_search.py \
  -q "placement routing" "physical design" \
  -y 2024-2026 \
  --venue-file assets/venues_eda.example.json \
  --topic-file assets/topics_eda.example.json \
  -o eda_papers.csv
```

## 配置檔格式

### config.json 結構

```json
{
  "queries": ["query1", "query2"],
  "year_range": "2024-2026",
  "venues": ["NeurIPS", "ICML"],
  "topics": ["RL", "DT"],
  "output": "papers.csv",
  "limit": 10000
}
```

### topics.json 結構

```json
{
  "RL": ["reinforcement\\s+learning", "policy\\s+gradient", "q-?learning"],
  "DT": ["decision\\s+transformer", "trajectory\\s+transformer"]
}
```

### venues.json 結構

```json
{
  "NeurIPS": ["neurips", "neural\\s+information\\s+processing\\s+systems"],
  "ICCAD": ["iccad", "computer-aided\\s+design"]
}
```

## 內建領域

### AI/ML 領域會議
- AAAI, IJCAI, NeurIPS, ICML, ICLR, KDD
- CVPR, ACL, EMNLP

### AI/ML 領域主題
- RL (Reinforcement Learning)
- DT (Decision Transformer)
- ICRL (In-Context RL)
- LLM, Diffusion

### EDA/VLSI 領域會議
- **期刊**: TCAD, TODAES, TVLSI, TCAS-I, TCAS-II
- **頂會**: DAC, ICCAD, DATE, ASPDAC
- **專題**: ISPD, ISQED, GLSVLSI, ISCAS, ISSCC
- **FPGA**: FPGA, FPL
- **測試**: ITC, VTS, ETS, ATS
- **低功耗**: ISLPED

### EDA/VLSI 領域主題
- PD (Physical Design)
- ML4EDA (ML for EDA)
- Logic (Logic Synthesis)
- Verification (Formal Verification)
- Timing (Timing Analysis)
- Power (Power Optimization)
- Test (DFT/ATPG)
- FPGA, Analog, 3DIC, Security

## 輸出格式

CSV 檔案包含以下欄位：
- 標題
- 摘要
- 連結
- 作者
- 日期
- 會議
- 主題
- 引用次數

## 注意事項

### API 限制

- **無需 API Key**: 大多數情況下可使用公共速率限制
- **速率限制**: 公共用戶共享 1000 請求/秒，可能遇到 429 錯誤
- **建議**: 大量搜尋時使用 `--limit` 參數控制數量

### 常見問題

1. **429 Too Many Requests**
   - 等待一段時間後重試
   - 減少 `-l` (limit) 參數值
   - 申請 API Key 獲得更高限制

2. **沒有符合的論文**
   - 檢查 `--venues` 和 `--topics` 是否過於嚴格
   - 嘗試更寬鬆的搜尋詞
   - **重要**: 使用 `--venue-file` 時必須同時使用對應的 `--topic-file`
     - EDA 領域需同時指定 `--venue-file assets/venues_eda.example.json --topic-file assets/topics_eda.example.json`
     - 若只用 `--venue-file` 會使用預設 AI 主題，導致 EDA 論文被過濾
   - 若要取消主題過濾，可建立空的 topics.json: `{}`

3. **會議名稱不正確**
   - 編輯 `assets/venues_*.example.json` 添加新的匹配模式
   - 使用正則表達式匹配多種寫法

### 正則表達式提示

配置檔中的關鍵詞使用正則表達式：
- `\s+` = 一個或多個空白
- `\b` = 單詞邊界
- `-?` = 可選的連字符
- 預設不區分大小寫

範例：
- `"reinforcement\\s+learning"` 匹配 "reinforcement learning"
- `"\\bdac\\b"` 匹配 "DAC" 但不匹配 "DACademy"

## 相關檔案

```
s2_paper_search/
├── SKILL.md                  # Agent 使用指南
├── README.md                 # 詳細說明文件
├── requirements.txt          # 依賴套件
├── scripts/
│   └── s2_search.py          # 主程式
└── assets/
    ├── config_ai.example.json    # AI 領域配置
    ├── config_eda.example.json   # EDA 領域配置
    ├── topics_ai.example.json    # AI 主題關鍵詞
    ├── topics_eda.example.json   # EDA 主題關鍵詞
    ├── venues_ai.example.json    # AI 會議/期刊
    └── venues_eda.example.json   # EDA 會議/期刊
```

## 相關連結

- Semantic Scholar API: https://api.semanticscholar.org/api-docs/graph
- 申請 API Key: https://www.semanticscholar.org/product/api
