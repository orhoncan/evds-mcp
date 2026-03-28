"""EVDS API async client with retry and structured error responses."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pandas as pd

BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
TIMEOUT = 60.0
MAX_RETRIES = 3
BACKOFF_BASE = 1.0

FREKANS = {
    "gunluk": 1, "isgunu": 2, "haftalik": 3, "ayda2": 4,
    "aylik": 5, "ceyreklik": 6, "6aylik": 7, "yillik": 8,
}

FORMUL = {
    "duzey": 0, "yuzde_degisim": 1, "fark": 2,
    "yillik_yuzde": 3, "yillik_fark": 4,
    "yilsonu_yuzde": 5, "yilsonu_fark": 6,
    "hareketli_ort": 7, "hareketli_toplam": 8,
}


def _error(kod: str, mesaj: str, oneri: str = "") -> dict:
    """Build structured error dict."""
    result = {"hata": True, "kod": kod, "mesaj": mesaj}
    if oneri:
        result["oneri"] = oneri
    return result


class EVDSClient:
    """Async EVDS API client."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def _request(self, url: str) -> dict | list | None:
        """Make HTTP request with retry. Returns parsed JSON or error dict."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as http:
                    resp = await http.get(
                        url,
                        headers={"key": self.api_key},
                        timeout=TIMEOUT,
                    )
                if resp.status_code == 403:
                    return _error(
                        "API_KEY_GECERSIZ",
                        "API anahtarı geçersiz veya süresi dolmuş.",
                        "https://evds2.tcmb.gov.tr adresinden yeni key alın.",
                    )
                if resp.status_code == 404:
                    return _error("SERI_BULUNAMADI", "İstenen kaynak bulunamadı.")
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE * (2 ** attempt))
            except httpx.HTTPStatusError as e:
                if 500 <= e.response.status_code < 600 and attempt < MAX_RETRIES - 1:
                    last_error = e
                    await asyncio.sleep(BACKOFF_BASE * (2 ** attempt))
                else:
                    return _error("BAGLANTI_HATASI", f"HTTP hatası: {e.response.status_code}")

        return _error("BAGLANTI_HATASI", f"Bağlantı hatası ({MAX_RETRIES} deneme sonrası): {last_error}")

    async def kategorileri_getir(self) -> list[dict] | dict:
        """Fetch all top-level categories."""
        result = await self._request(f"{BASE_URL}/categories/type=json")
        if isinstance(result, dict) and result.get("hata"):
            return result
        return result if isinstance(result, list) else []

    async def veri_gruplari(self, kategori_id: int | None = None) -> list[dict] | dict:
        """Fetch data groups, optionally filtered by category."""
        if kategori_id:
            url = f"{BASE_URL}/datagroups/mode=2&code={kategori_id}&type=json"
        else:
            url = f"{BASE_URL}/datagroups/mode=0&type=json"
        result = await self._request(url)
        if isinstance(result, dict) and result.get("hata"):
            return result
        return result if isinstance(result, list) else []

    # Popüler seri kısayolları — API araması öncesi hızlı eşleşme
    _POPULER = {
        "enflasyon": [("TP.FG.J0", "TÜFE - Genel Endeks (2003=100)", "bie_tukfiy")],
        "tüfe": [("TP.FG.J0", "TÜFE - Genel Endeks (2003=100)", "bie_tukfiy")],
        "üfe": [("TP.FG.J1", "ÜFE - Yurt İçi Üretici Fiyat Endeksi (2003=100)", "bie_ufeyeni")],
        "döviz": [
            ("TP.DK.USD.A", "USD/TRY Alış", "bie_dkdovytl"),
            ("TP.DK.EUR.A", "EUR/TRY Alış", "bie_dkdovytl"),
            ("TP.DK.GBP.A", "GBP/TRY Alış", "bie_dkdovytl"),
        ],
        "dolar": [("TP.DK.USD.A", "USD/TRY", "bie_dkdovytl")],
        "usd": [("TP.DK.USD.A", "USD/TRY", "bie_dkdovytl")],
        "euro": [("TP.DK.EUR.A", "EUR/TRY", "bie_dkdovytl")],
        "eur": [("TP.DK.EUR.A", "EUR/TRY", "bie_dkdovytl")],
        "sterlin": [("TP.DK.GBP.A", "GBP/TRY", "bie_dkdovytl")],
        "gbp": [("TP.DK.GBP.A", "GBP/TRY", "bie_dkdovytl")],
        "altın": [("TP.DK.ALT.A", "Altın TRY/Gram", "bie_dkaltytl")],
        "faiz": [("TP.PF.FF.GUN", "TCMB Politika Faizi", "bie_pfaizler")],
        "politika faizi": [("TP.PF.FF.GUN", "TCMB Politika Faizi", "bie_pfaizler")],
        "işsizlik": [("TP.UR.U01", "İşsizlik Oranı (%)", "bie_isgucu")],
        "gsyh": [("TP.GSYIH01.GSYIH.Z.TUFE", "GSYH Harcama Yöntemiyle (Sabit Fiyatlarla)", "bie_gsyihgelhiz")],
        "gdp": [("TP.GSYIH01.GSYIH.Z.TUFE", "GSYH Harcama Yöntemiyle (Sabit Fiyatlarla)", "bie_gsyihgelhiz")],
        "cari denge": [("TP.ODEMELER.CARI1", "Cari İşlemler Dengesi", "bie_odenegdenam")],
        "cari açık": [("TP.ODEMELER.CARI1", "Cari İşlemler Dengesi", "bie_odenegdenam")],
        "rezerv": [("TP.AB.A01", "TCMB Brüt Döviz Rezervleri", "bie_abres")],
    }

    async def seri_ara(self, anahtar_kelime: str, limit: int = 25) -> dict:
        """Search for series by keyword.

        1. Check popular series shortcut dict — if exact match, return immediately
        2. Fetch all data groups, filter by keyword
        3. For matching groups, fetch series lists (up to limit)

        Returns:
            {"sonuclar": [...], "toplam": int}
        """
        kelime = anahtar_kelime.lower().strip()

        # Quick match from popular series
        populer = []
        gorulmus: set[str] = set()
        for k, seriler in self._POPULER.items():
            if k in kelime or kelime in k:
                for kod, ad, grup in seriler:
                    if kod not in gorulmus:
                        gorulmus.add(kod)
                        populer.append({
                            "seri_kodu": kod,
                            "seri_adi": ad,
                            "frekans": "",
                            "grup_kodu": grup,
                            "grup_adi": "",
                        })

        # If we have an exact popular match, skip the expensive API scan
        if kelime in self._POPULER:
            return {"sonuclar": populer, "toplam": len(populer)}

        # API search: fetch data groups, filter by keyword
        gruplar = await self.veri_gruplari()
        if isinstance(gruplar, dict) and gruplar.get("hata"):
            if populer:
                return {"sonuclar": populer, "toplam": len(populer)}
            return {"sonuclar": [], "toplam": 0}

        eslesen_gruplar = []
        for g in gruplar:
            ad = g.get("DATAGROUP_NAME_TR", "").lower()
            kod = g.get("DATAGROUP_CODE", "").lower()
            if kelime in ad or kelime in kod:
                eslesen_gruplar.append(g)

        sonuclar = list(populer)
        toplam_bulunan = len(populer)

        for g in eslesen_gruplar:
            grup_kodu = g["DATAGROUP_CODE"]
            grup_adi = g.get("DATAGROUP_NAME_TR", "")
            frekans = g.get("FREQUENCY_STR", "")

            seriler = await self.seri_listesi(grup_kodu)
            if isinstance(seriler, dict) and seriler.get("hata"):
                continue

            for s in seriler:
                seri_kodu = s.get("SERIE_CODE", "")
                if seri_kodu and seri_kodu not in gorulmus:
                    gorulmus.add(seri_kodu)
                    toplam_bulunan += 1
                    if len(sonuclar) < limit:
                        sonuclar.append({
                            "seri_kodu": seri_kodu,
                            "seri_adi": s.get("SERIE_NAME_TR", ""),
                            "frekans": s.get("FREQUENCY_STR", frekans),
                            "grup_kodu": grup_kodu,
                            "grup_adi": grup_adi,
                        })

        return {"sonuclar": sonuclar, "toplam": toplam_bulunan}

    async def seri_listesi(self, grup_kodu: str) -> list[dict] | dict:
        """Fetch series in a data group."""
        result = await self._request(f"{BASE_URL}/serieList/code={grup_kodu}&type=json")
        if isinstance(result, dict) and result.get("hata"):
            return result
        return result if isinstance(result, list) else []

    async def veri_cek(
        self,
        seriler: list[str],
        baslangic: str,
        bitis: str,
        frekans: str | None = None,
        formul: str | None = None,
    ) -> dict:
        """Fetch time series data."""
        seri_str = "-".join(seriler)
        url = f"{BASE_URL}/series={seri_str}&startDate={baslangic}&endDate={bitis}&type=json"

        if frekans:
            kod = FREKANS.get(frekans.lower(), frekans)
            url += f"&frequency={kod}"
        if formul:
            kod = FORMUL.get(formul.lower(), formul)
            url += f"&formulas={kod}"

        result = await self._request(url)
        if isinstance(result, dict) and result.get("hata"):
            return result

        items = result.get("items", []) if isinstance(result, dict) else []
        if not items:
            return _error("VERI_YOK", "Belirtilen tarih aralığında veri bulunamadı.")

        return self._parse_veri(seriler, baslangic, bitis, items)

    def _parse_veri(
        self, seriler: list[str], baslangic: str, bitis: str, items: list[dict]
    ) -> dict:
        """Parse EVDS items into structured output."""
        df = pd.DataFrame(items)

        # Find date column
        tarih_col = "Tarih" if "Tarih" in df.columns else df.columns[0]

        # Parse dates
        tarih_str = str(df[tarih_col].iloc[0])
        parcalar = tarih_str.split("-")
        if len(parcalar[0]) == 4:
            df[tarih_col] = pd.to_datetime(df[tarih_col], format="%Y-%m")
        else:
            df[tarih_col] = pd.to_datetime(df[tarih_col], format="%d-%m-%Y")

        # Convert numeric columns
        for col in df.columns:
            if col != tarih_col and col not in ("UNIXTIME", "YEARWEEK"):
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Drop unnecessary columns
        df = df.drop(columns=[c for c in ("UNIXTIME", "YEARWEEK") if c in df.columns])

        # Format output
        veri = []
        for _, row in df.iterrows():
            entry = {"tarih": row[tarih_col].strftime("%Y-%m-%d")}
            for col in df.columns:
                if col != tarih_col:
                    val = row[col]
                    entry[col] = round(float(val), 4) if pd.notna(val) else None
            veri.append(entry)

        return {
            "seriler": seriler,
            "tarih_araligi": [baslangic, bitis],
            "gozlem_sayisi": len(veri),
            "veri": veri,
        }
