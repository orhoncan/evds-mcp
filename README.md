# EVDS MCP Sunucusu

TCMB Elektronik Veri Dağıtım Sistemi (EVDS) için [Model Context Protocol](https://modelcontextprotocol.io/) sunucusu. Becerilere kıyasla daha öngörülebilir düzende çıktı sunar.

Claude, GPT ve diğer LLM'ler üzerinden doğal dilde TCMB verilerine erişim sağlar. Döviz kurları, enflasyon, faiz, GSYH, cari denge ve binlerce ekonomik seriye ulaşımı kolaylaştırır.

## Kurulum

[EVDS](https://evds3.tcmb.gov.tr) sitesinden ücretsiz API anahtarı alın, ardından tek komutla kurun.

```bash
claude mcp add -e EVDS_API_KEY=ANAHTARINIZ evds-mcp -- uvx --from git+https://github.com/orhoncan/evds-mcp evds-mcp
```

API anahtarını config dosyasında tutmayı tercih ederseniz:

```bash
echo '{"api_key": "ANAHTARINIZ"}' > ~/.evds-mcp.json
claude mcp add evds-mcp -- uvx --from git+https://github.com/orhoncan/evds-mcp evds-mcp
```



### Claude Desktop / Kaynak koddan çalıştırma
#### Claude Desktop

`claude_desktop_config.json` dosyasına ekleyin:

```json
{
  "mcpServers": {
    "evds-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/orhoncan/evds-mcp", "evds-mcp"],
      "env": {
        "EVDS_API_KEY": "ANAHTARINIZ"
      }
    }
  }
}
```

### Kaynak Koddan Çalıştırma

```bash
git clone https://github.com/orhoncan/evds-mcp.git
cd evds-mcp
uv sync
uv run evds-mcp
```

### Claude'dan vb. İsteme
Doğrudan repo bağlantısını paylaşarak Claude'dan ya da diğer sağlayıcılardan kurulum yapmasını isteyebilirsiniz.

## Araçlar

| Araç | Açıklama |
|------|----------|
| `evds_ara` | Anahtar kelimeyle seri arar. Popüler seriler (enflasyon, döviz, faiz, usd, gsyh vb.) için anında eşleşme. |
| `evds_meta` | Bir serinin metadata'sını getirir: ad, frekans, tarih aralığı, birim. |
| `evds_cek` | Bir veya daha fazla serinin verisini çeker. Frekans dönüşümü ve formül desteği. |
| `evds_analiz` | Veri çeker ve istatistiksel analiz uygular: özet, yüzde değişim, korelasyon, OLS, ARIMA. |

## Kullanım Örnekleri

### Seri Arama

```
> evds_ara("usd")
→ TP.DK.USD.A — USD/TRY

> evds_ara("enflasyon")
→ TP.FG.J0 — TÜFE Genel Endeks (2003=100)
```

Popüler aramalar (`usd`, `eur`, `altın`, `faiz`, `enflasyon`, `gsyh`, `işsizlik`, `cari açık`, `rezerv` vb.) API'ye gitmeden anında sonuç döner. Bu liste zamanla genişleyecek ama ne kadar net yönlendirirseniz o kadar verimli çalışır. Bazı sık kullanılan kelimeler çok uzun listeler döndürdüğü için performans kaybı olabiliyor.

### Veri Çekme

```
> evds_cek(["TP.DK.USD.A"], baslangic="01-01-2025", bitis="28-03-2026")
→ 29 gözlem, günlük USD/TRY kurları

> evds_cek(["TP.FG.J0"], frekans="aylik", formul="yillik_yuzde")
→ Yıllık TÜFE (%)
```

**Frekans:** `gunluk`, `haftalik`, `aylik`, `ceyreklik`, `yillik`
**Formül:** `duzey`, `yuzde_degisim`, `fark`, `yillik_yuzde`, `yillik_fark`

### Analiz

```
> evds_analiz(["TP.FG.J0"], analiz_turu="ozet")
→ Tanımlayıcı istatistikler + trend tespiti

> evds_analiz(["TP.DK.USD.A", "TP.FG.J0"], analiz_turu="korelasyon")
→ Korelasyon matrisi + sözel yorumlama
ya da aynı sonuç için;
> USD alış kuru ile TÜFE arasında son 1 yıllık korelasyona bak.
→ Korelasyon matrisi + sözel yorumlama

> evds_analiz(["TP.FG.J0"], analiz_turu="arima", parametreler={"tahmin_donemi": 6})
→ ARIMA/SARIMA tahmini + güven aralıkları
```

**Analiz türleri:**
- `ozet` — Ortalama, std, min/max, trend
- `degisim` — Yüzde değişim (aylık/yıllık/dönemsel)
- `korelasyon` — Pearson/Spearman korelasyon matrisi
- `ols` — OLS regresyon (R², F-testi, Durbin-Watson)
- `arima` — ARIMA/SARIMA tahmin + güven aralıkları

## Ekran Görüntüleri

<img width="811" height="335" alt="image" src="https://github.com/user-attachments/assets/f8cfd940-4eb2-481c-94b6-19270e1e616c" />
<p></p>
<p></p>
<img width="954" height="189" alt="image" src="https://github.com/user-attachments/assets/185d3099-d033-4f40-be4e-73eb0886df8b" />
<p></p>
<p></p>
<img width="982" height="480" alt="image" src="https://github.com/user-attachments/assets/db9cd61b-a7a4-4b9c-8aac-a4365ddf0899" />
<p></p>


## Yapılacaklar

- Serilerin aranması ve kullanılması konusunda iyileştirmeler
- Ekonometrik modellerin çeşitlendirilmesi

## Gereksinimler

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) (önerilen) veya pip
- TCMB EVDS API anahtarı (ücretsiz)

## Lisans

MIT
