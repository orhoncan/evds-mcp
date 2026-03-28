# src/evds_mcp/server.py
"""EVDS MCP Server — 4 tools for TCMB data access and analysis."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastmcp import FastMCP

from evds_mcp.api import EVDSClient
from evds_mcp.analysis import (
    analiz_arima,
    analiz_degisim,
    analiz_korelasyon,
    analiz_ols,
    analiz_ozet,
    ozet_template,
)
from evds_mcp.config import api_key_missing_error, resolve_api_key

_client: EVDSClient | None = None


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize EVDS client with API key at startup."""
    global _client
    sys.stderr.write("EVDS MCP: starting...\n")
    key = resolve_api_key()
    if key:
        _client = EVDSClient(api_key=key)
        sys.stderr.write("EVDS MCP: API key loaded\n")
    else:
        sys.stderr.write("EVDS MCP: no API key found — tools will return error\n")
    yield {}
    sys.stderr.write("EVDS MCP: shutting down\n")


mcp = FastMCP("EVDS", lifespan=server_lifespan)


def _check_client() -> dict | None:
    """Return error dict if client not initialized."""
    if _client is None:
        return api_key_missing_error()
    return None


def _default_dates(baslangic: str, bitis: str) -> tuple[str, str]:
    """Fill in default dates if not provided."""
    if not bitis:
        bitis = datetime.now().strftime("%d-%m-%Y")
    if not baslangic:
        one_year_ago = datetime.now() - timedelta(days=365)
        baslangic = one_year_ago.strftime("%d-%m-%Y")
    return baslangic, bitis


@mcp.tool(
    name="evds_ara",
    description=(
        "EVDS'de anahtar kelimeyle seri arar. Kategorileri ve veri gruplarını tarayarak "
        "eşleşen serileri döner. Popüler seriler (enflasyon, döviz, faiz, usd, eur, gsyh vb.) "
        "için hızlı eşleşme sağlar. Sonuçlar limit ile sınırlandırılır (varsayılan 25). "
        "Dönen: seri_kodu, seri_adi, frekans, grup_kodu, grup_adi, toplam (gerçek toplam)."
    ),
)
async def evds_ara(anahtar_kelime: str, limit: int = 25) -> dict:
    """Search EVDS series by keyword.

    Args:
        anahtar_kelime: Search term in Turkish (e.g. "enflasyon", "döviz", "faiz", "usd")
        limit: Maximum number of results to return (default 25)
    """
    err = _check_client()
    if err:
        return err
    return await _client.seri_ara(anahtar_kelime, limit=limit)


@mcp.tool(
    name="evds_meta",
    description=(
        "Bir EVDS serisinin metadata'sını getirir: seri adı, frekans, başlangıç/bitiş tarihi, "
        "birim, kaynak. Veri çekmeden önce seri hakkında bilgi almak için kullanın."
    ),
)
async def evds_meta(seri_kodu: str) -> dict:
    """Get metadata for a specific series.

    Args:
        seri_kodu: Series code (e.g. "TP.FG.J0")
    """
    err = _check_client()
    if err:
        return err

    gruplar = await _client.veri_gruplari()
    if isinstance(gruplar, dict) and gruplar.get("hata"):
        return gruplar

    for g in gruplar:
        grup_kodu = g.get("DATAGROUP_CODE", "")
        seriler = await _client.seri_listesi(grup_kodu)
        if isinstance(seriler, dict) and seriler.get("hata"):
            continue
        for s in seriler:
            if s.get("SERIE_CODE") == seri_kodu:
                return {
                    "seri_kodu": seri_kodu,
                    "seri_adi": s.get("SERIE_NAME_TR", ""),
                    "frekans": s.get("FREQUENCY_STR", g.get("FREQUENCY_STR", "")),
                    "baslangic": s.get("START_DATE", ""),
                    "bitis": s.get("END_DATE", ""),
                    "birim": s.get("DATASOURCE_TR", ""),
                    "kaynak": g.get("DATASOURCE_TR", "TCMB"),
                }

    return {"hata": True, "kod": "SERI_BULUNAMADI", "mesaj": f"Seri bulunamadı: {seri_kodu}"}


@mcp.tool(
    name="evds_cek",
    description=(
        "EVDS'den bir veya daha fazla serinin verisini çeker. Tarih formatı: gg-aa-yyyy. "
        "Varsayılan: son 1 yıl. Opsiyonel frekans dönüşümü (gunluk, aylik, yillik vb.) "
        "ve formül (duzey, yuzde_degisim, yillik_yuzde vb.) uygulanabilir."
    ),
)
async def evds_cek(
    seriler: list[str],
    baslangic: str = "",
    bitis: str = "",
    frekans: str = "",
    formul: str = "",
) -> dict:
    """Fetch time series data from EVDS.

    Args:
        seriler: Series codes (e.g. ["TP.FG.J0", "TP.DK.USD.A"])
        baslangic: Start date dd-mm-yyyy (default: 1 year ago)
        bitis: End date dd-mm-yyyy (default: today)
        frekans: Frequency conversion (gunluk, haftalik, aylik, ceyreklik, yillik)
        formul: Formula (duzey, yuzde_degisim, fark, yillik_yuzde, yillik_fark)
    """
    err = _check_client()
    if err:
        return err

    baslangic, bitis = _default_dates(baslangic, bitis)
    return await _client.veri_cek(
        seriler, baslangic, bitis,
        frekans=frekans or None,
        formul=formul or None,
    )


@mcp.tool(
    name="evds_analiz",
    description=(
        "EVDS'den veri çeker ve istatistiksel analiz uygular. Tek adımda veri + analiz. "
        "Analiz türleri: ozet (tanımlayıcı istatistikler), degisim (yüzde değişim), "
        "korelasyon (korelasyon matrisi), ols (OLS regresyon), arima (ARIMA tahmin). "
        "Her çıktı deterministik — aynı girdi her zaman aynı sonucu verir."
    ),
)
async def evds_analiz(
    seriler: list[str],
    analiz_turu: str,
    baslangic: str = "",
    bitis: str = "",
    parametreler: dict | None = None,
) -> dict:
    """Fetch data and run analysis in one step.

    Args:
        seriler: Series codes (e.g. ["TP.FG.J0"])
        analiz_turu: Analysis type — ozet, degisim, korelasyon, ols, arima
        baslangic: Start date dd-mm-yyyy (default: 1 year ago)
        bitis: End date dd-mm-yyyy (default: today)
        parametreler: Type-specific params. degisim: {"periyot": "aylik"|"yillik"|"donemsel"}.
                     korelasyon: {"metot": "pearson"|"spearman"}.
                     ols: {"bagimli": "SERIES_CODE"}.
                     arima: {"tahmin_donemi": 12, "mevsimsel": true}.
    """
    err = _check_client()
    if err:
        return err

    if analiz_turu not in ("ozet", "degisim", "korelasyon", "ols", "arima"):
        return {
            "hata": True,
            "kod": "ANALIZ_HATASI",
            "mesaj": f"Geçersiz analiz türü: {analiz_turu}. Geçerli: ozet, degisim, korelasyon, ols, arima",
        }

    params = parametreler or {}
    baslangic, bitis = _default_dates(baslangic, bitis)

    # Fetch data
    veri_sonuc = await _client.veri_cek(seriler, baslangic, bitis)
    if isinstance(veri_sonuc, dict) and veri_sonuc.get("hata"):
        return veri_sonuc

    # Convert to DataFrame
    import pandas as pd
    rows = veri_sonuc["veri"]
    df = pd.DataFrame(rows)
    df["tarih"] = pd.to_datetime(df["tarih"])
    df = df.set_index("tarih")

    # Run analysis
    try:
        if analiz_turu == "ozet":
            sonuc = analiz_ozet(df)
        elif analiz_turu == "degisim":
            sonuc = analiz_degisim(df, periyot=params.get("periyot", "aylik"))
        elif analiz_turu == "korelasyon":
            sonuc = analiz_korelasyon(df, metot=params.get("metot", "pearson"))
        elif analiz_turu == "ols":
            bagimli = params.get("bagimli")
            if not bagimli:
                return {
                    "hata": True,
                    "kod": "ANALIZ_HATASI",
                    "mesaj": "OLS analizi için 'bagimli' parametresi gerekli.",
                }
            sonuc = analiz_ols(df, bagimli=bagimli)
        elif analiz_turu == "arima":
            if len(seriler) != 1:
                return {
                    "hata": True,
                    "kod": "ANALIZ_HATASI",
                    "mesaj": "ARIMA analizi tek seri üzerinde çalışır.",
                }
            sonuc = analiz_arima(
                df[df.columns[0]],
                tahmin_donemi=params.get("tahmin_donemi", 12),
                mevsimsel=params.get("mevsimsel", True),
            )
    except Exception as e:
        return {"hata": True, "kod": "ANALIZ_HATASI", "mesaj": str(e)}

    if isinstance(sonuc, dict) and sonuc.get("hata"):
        return sonuc

    ozet_text = ozet_template(analiz_turu, sonuc)

    return {
        "analiz_turu": analiz_turu,
        "seriler": seriler,
        "tarih_araligi": [baslangic, bitis],
        "parametreler": params,
        "sonuc": sonuc,
        "ozet": ozet_text,
    }
