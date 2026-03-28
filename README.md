# evds-mcp

TCMB Elektronik Veri Dağıtım Sistemi (EVDS) için [Model Context Protocol](https://modelcontextprotocol.io/) sunucusu.

Claude, GPT ve diğer LLM'ler üzerinden doğal dilde TCMB verilerine erişim sağlar: döviz kurları, enflasyon, faiz, GSYH, cari denge ve binlerce ekonomik seri.

## Araçlar

| Araç | Açıklama |
|------|----------|
| `evds_ara` | Anahtar kelimeyle seri arar. Popüler seriler (enflasyon, döviz, faiz, usd, gsyh vb.) için anında eşleşme. |
| `evds_meta` | Bir serinin metadata'sını getirir: ad, frekans, tarih aralığı, birim. |
| `evds_cek` | Bir veya daha fazla serinin verisini çeker. Frekans dönüşümü ve formül desteği. |
| `evds_analiz` | Veri çeker ve istatistiksel analiz uygular: özet, yüzde değişim, korelasyon, OLS, ARIMA. |

## Kurulum

### 1. API Anahtarı

[EVDS](https://evds2.tcmb.gov.tr) sitesinden ücretsiz API anahtarı alın. Sonra iki yöntemden biriyle tanımlayın:

```bash
# Seçenek A: Config dosyası (önerilen)
echo '{"api_key": "ANAHTARINIZ"}' > ~/.evds-mcp.json

# Seçenek B: Ortam değişkeni
export EVDS_API_KEY=ANAHTARINIZ
```

### 2. Claude Code / Claude Desktop

Claude Code `settings.json` veya Claude Desktop `claude_desktop_config.json` dosyasına ekleyin:

```json
{
  "mcpServers": {
    "evds-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/EVDS-MCP/YOLU", "evds-mcp", "serve"]
    }
  }
}
```

### 3. Doğrudan Çalıştırma

```bash
git clone https://github.com/orhoncan/evds-mcp.git
cd evds-mcp
uv sync
uv run evds-mcp serve
```

## Kullanım Örnekleri

### Seri Arama

```
> evds_ara("usd")
→ TP.DK.USD.A — USD/TRY

> evds_ara("enflasyon")
→ TP.FG.J0 — TÜFE Genel Endeks (2003=100)
```

Popüler aramalar (`usd`, `eur`, `altın`, `faiz`, `enflasyon`, `gsyh`, `işsizlik`, `cari açık`, `rezerv` vb.) API'ye gitmeden anında sonuç döner.

### Veri Çekme

```
> evds_cek(["TP.DK.USD.A"], baslangic="01-01-2025", bitis="28-03-2026")
→ 29 gözlem, günlük USD/TRY kurları

> evds_cek(["TP.FG.J0"], frekans="aylik", formul="yillik_yuzde")
→ Yıllık TÜFE enflasyonu (%)
```

**Frekans:** `gunluk`, `haftalik`, `aylik`, `ceyreklik`, `yillik`
**Formül:** `duzey`, `yuzde_degisim`, `fark`, `yillik_yuzde`, `yillik_fark`

### Analiz

```
> evds_analiz(["TP.FG.J0"], analiz_turu="ozet")
→ Tanımlayıcı istatistikler + trend tespiti

> evds_analiz(["TP.DK.USD.A", "TP.FG.J0"], analiz_turu="korelasyon")
→ Korelasyon matrisi + sözel yorum

> evds_analiz(["TP.FG.J0"], analiz_turu="arima", parametreler={"tahmin_donemi": 6})
→ ARIMA/SARIMA tahmini + güven aralıkları
```

**Analiz türleri:**
- `ozet` — Ortalama, std, min/max, trend
- `degisim` — Yüzde değişim (aylık/yıllık/dönemsel)
- `korelasyon` — Pearson/Spearman korelasyon matrisi
- `ols` — OLS regresyon (R², F-testi, Durbin-Watson)
- `arima` — ARIMA/SARIMA tahmin + güven aralıkları

## Gereksinimler

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) (önerilen) veya pip
- TCMB EVDS API anahtarı (ücretsiz)

## Lisans

MIT
