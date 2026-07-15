"""EVDS API async client with retry and structured error responses."""

from __future__ import annotations

import asyncio
import re

import httpx
import pandas as pd

BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
TIMEOUT = 60.0
MAX_RETRIES = 3
BACKOFF_BASE = 1.0
MAX_ES_ZAMANLI_ISTEK = 8

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


def _tarih_parse(tarih: pd.Series) -> pd.Series:
    """Parse EVDS date column into datetime.

    EVDS returns different formats per frequency:
    - daily / business / weekly / biweekly: "dd-mm-yyyy"
    - monthly: "yyyy-m"
    - quarterly: "yyyy-Qn"
    - semiannual: "yyyy-Sn"
    - yearly: bare integer yyyy
    """
    s = tarih.astype(str).str.strip()
    ornek = s.iloc[0]

    if re.fullmatch(r"\d{4}", ornek):
        return pd.to_datetime(s, format="%Y")
    if re.fullmatch(r"\d{4}-Q\d", ornek):
        parcalar = s.str.extract(r"(\d{4})-Q(\d)")
        return pd.to_datetime(pd.DataFrame({
            "year": parcalar[0].astype(int),
            "month": (parcalar[1].astype(int) - 1) * 3 + 1,
            "day": 1,
        }))
    if re.fullmatch(r"\d{4}-S\d", ornek):
        parcalar = s.str.extract(r"(\d{4})-S(\d)")
        return pd.to_datetime(pd.DataFrame({
            "year": parcalar[0].astype(int),
            "month": (parcalar[1].astype(int) - 1) * 6 + 1,
            "day": 1,
        }))
    if re.fullmatch(r"\d{4}-\d{1,2}", ornek):
        return pd.to_datetime(s, format="%Y-%m")
    if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{4}", ornek):
        return pd.to_datetime(s, format="%d-%m-%Y")
    return pd.to_datetime(s, dayfirst=True, errors="coerce")


class EVDSClient:
    """Async EVDS API client with connection reuse and in-process caching."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._http: httpx.AsyncClient | None = None
        self._grup_cache: list[dict] | None = None
        self._seri_cache: dict[str, list[dict]] = {}

    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=TIMEOUT, headers={"key": self.api_key}
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()

    async def _request(self, url: str) -> dict | list | None:
        """Make HTTP request with retry. Returns parsed JSON or error dict."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._http_client().get(url)
                if resp.status_code == 403:
                    return _error(
                        "API_KEY_GECERSIZ",
                        "API anahtarı geçersiz veya süresi dolmuş.",
                        "https://evds2.tcmb.gov.tr adresinden yeni key alın.",
                    )
                if resp.status_code == 404:
                    return _error("SERI_BULUNAMADI", "İstenen kaynak bulunamadı.")
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError as e:
                    # EVDS occasionally returns HTML error pages with HTTP 200
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(BACKOFF_BASE * (2 ** attempt))
                        continue
                    return _error(
                        "GECERSIZ_YANIT",
                        "API JSON yerine geçersiz yanıt döndürdü (servis geçici olarak sorunlu olabilir).",
                    )
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
        """Fetch data groups, optionally filtered by category.

        The full (unfiltered) list is cached for the process lifetime.
        """
        if kategori_id is None and self._grup_cache is not None:
            return self._grup_cache
        if kategori_id:
            url = f"{BASE_URL}/datagroups/mode=2&code={kategori_id}&type=json"
        else:
            url = f"{BASE_URL}/datagroups/mode=0&type=json"
        result = await self._request(url)
        if isinstance(result, dict) and result.get("hata"):
            return result
        result = result if isinstance(result, list) else []
        if kategori_id is None and result:
            self._grup_cache = result
        return result

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
        "güven endeksi": [
            ("TP.GY1.N2", "Reel Kesim Güven Endeksi (ham)", "bie_rkgey2"),
            ("TP.GY1.N2.MA", "Reel Kesim Güven Endeksi (MA)", "bie_rkgema"),
        ],
        "rkge": [
            ("TP.GY1.N2", "Reel Kesim Güven Endeksi (ham)", "bie_rkgey2"),
            ("TP.GY1.N2.MA", "Reel Kesim Güven Endeksi (MA)", "bie_rkgema"),
        ],
        "kapasite": [
            ("TP.KKO2.IS.TOP", "Kapasite Kullanım Oranı - Toplam (ham)", "bie_kko2"),
            ("TP.KKO.MA", "Kapasite Kullanım Oranı (MA)", "bie_kkoisma"),
        ],
        "kko": [
            ("TP.KKO2.IS.TOP", "Kapasite Kullanım Oranı - Toplam (ham)", "bie_kko2"),
            ("TP.KKO.MA", "Kapasite Kullanım Oranı (MA)", "bie_kkoisma"),
        ],
        "tüketici güveni": [("TP.TGE1.N1", "Tüketici Güven Endeksi (ham)", "bie_mbgven2")],
        "tge": [("TP.TGE1.N1", "Tüketici Güven Endeksi (ham)", "bie_mbgven2")],
    }

    async def seri_ara(self, anahtar_kelime: str, limit: int = 25) -> dict:
        """Search for series by keyword.

        1. Check popular series shortcut dict — if exact match, return immediately
        2. Fetch all data groups, filter by keyword
        3. For matching groups, fetch series lists concurrently (up to limit)

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
            kod = (g.get("DATAGROUP_CODE") or "").lower()
            ad = (g.get("DATAGROUP_NAME") or g.get("DATAGROUP_NAME_TR") or "").lower()
            if kod and (kelime in ad or kelime in kod):
                eslesen_gruplar.append(g)

        # Fetch series lists for matching groups concurrently (bounded)
        sem = asyncio.Semaphore(MAX_ES_ZAMANLI_ISTEK)

        async def _liste(g: dict) -> list[dict] | dict:
            async with sem:
                return await self.seri_listesi(g["DATAGROUP_CODE"])

        listeler = await asyncio.gather(*(_liste(g) for g in eslesen_gruplar))

        sonuclar = list(populer)
        toplam_bulunan = len(populer)

        for g, seriler in zip(eslesen_gruplar, listeler):
            if isinstance(seriler, dict) and seriler.get("hata"):
                continue

            grup_kodu = g["DATAGROUP_CODE"]
            grup_adi = g.get("DATAGROUP_NAME") or g.get("DATAGROUP_NAME_TR") or ""
            frekans = g.get("FREQUENCY_STR", "")

            for s in seriler:
                seri_kodu = s.get("SERIE_CODE", "")
                if seri_kodu and seri_kodu not in gorulmus:
                    gorulmus.add(seri_kodu)
                    toplam_bulunan += 1
                    if len(sonuclar) < limit:
                        sonuclar.append({
                            "seri_kodu": seri_kodu,
                            "seri_adi": s.get("SERIE_NAME") or s.get("SERIE_NAME_TR") or "",
                            "frekans": s.get("FREQUENCY_STR", frekans),
                            "grup_kodu": grup_kodu,
                            "grup_adi": grup_adi,
                        })

        return {"sonuclar": sonuclar, "toplam": toplam_bulunan}

    async def seri_listesi(self, grup_kodu: str) -> list[dict] | dict:
        """Fetch series in a data group. Successful responses are cached."""
        if grup_kodu in self._seri_cache:
            return self._seri_cache[grup_kodu]
        result = await self._request(f"{BASE_URL}/serieList/code={grup_kodu}&type=json")
        if isinstance(result, dict) and result.get("hata"):
            return result
        result = result if isinstance(result, list) else []
        self._seri_cache[grup_kodu] = result
        return result

    async def seri_bul(self, seri_kodu: str) -> dict:
        """Find a series across all data groups and return its metadata.

        Scans group series lists concurrently and stops at the first match.
        """
        gruplar = await self.veri_gruplari()
        if isinstance(gruplar, dict) and gruplar.get("hata"):
            return gruplar

        sem = asyncio.Semaphore(MAX_ES_ZAMANLI_ISTEK)

        async def _tara(g: dict) -> dict | None:
            grup_kodu = g.get("DATAGROUP_CODE") or ""
            if not grup_kodu:
                return None
            async with sem:
                seriler = await self.seri_listesi(grup_kodu)
            if isinstance(seriler, dict):
                return None
            for s in seriler:
                if s.get("SERIE_CODE") == seri_kodu:
                    return {
                        "seri_kodu": seri_kodu,
                        "seri_adi": s.get("SERIE_NAME") or s.get("SERIE_NAME_TR") or "",
                        "frekans": s.get("FREQUENCY_STR", g.get("FREQUENCY_STR", "")),
                        "baslangic": s.get("START_DATE", ""),
                        "bitis": s.get("END_DATE", ""),
                        "birim": s.get("DATASOURCE") or s.get("DATASOURCE_TR") or "",
                        "kaynak": g.get("DATASOURCE", "TCMB"),
                    }
            return None

        tasks = [asyncio.create_task(_tara(g)) for g in gruplar]
        try:
            for fut in asyncio.as_completed(tasks):
                sonuc = await fut
                if sonuc is not None:
                    return sonuc
        finally:
            for t in tasks:
                t.cancel()

        return _error("SERI_BULUNAMADI", f"Seri bulunamadı: {seri_kodu}")

    async def veri_cek(
        self,
        seriler: list[str],
        baslangic: str,
        bitis: str,
        frekans: str | None = None,
        formul: str | None = None,
    ) -> dict:
        """Fetch time series data."""
        seriler = [s.strip() for s in seriler if s and s.strip()]
        if not seriler:
            return _error(
                "SERI_KODU_EKSIK",
                "En az bir seri kodu gerekli.",
                "Örnek: [\"TP.FG.J0\"] — kodları evds_ara ile bulabilirsiniz.",
            )

        seri_str = "-".join(seriler)
        url = f"{BASE_URL}/series={seri_str}&startDate={baslangic}&endDate={bitis}&type=json"

        # Bilinmeyen filtre adı sessizce URL'ye sızarsa EVDS beklenmedik/boş
        # sonuç döner ve bu geçerli sonuç sanılabilir; ham sayısal kod geçişine
        # izin ver, gerisini ağa çıkmadan reddet.
        if frekans:
            if frekans.lower() in FREKANS:
                url += f"&frequency={FREKANS[frekans.lower()]}"
            elif frekans.isdigit():
                url += f"&frequency={frekans}"
            else:
                return _error(
                    "PARAMETRE_GECERSIZ",
                    f"Geçersiz frekans: {frekans}",
                    f"Geçerli değerler: {', '.join(FREKANS)}",
                )
        if formul:
            if formul.lower() in FORMUL:
                url += f"&formulas={FORMUL[formul.lower()]}"
            elif formul.isdigit():
                url += f"&formulas={formul}"
            else:
                return _error(
                    "PARAMETRE_GECERSIZ",
                    f"Geçersiz formül: {formul}",
                    f"Geçerli değerler: {', '.join(FORMUL)}",
                )

        result = await self._request(url)
        if isinstance(result, dict) and result.get("hata"):
            return result

        items = result.get("items", []) if isinstance(result, dict) else []
        if not items:
            return _error("VERI_YOK", "Belirtilen tarih aralığında veri bulunamadı.")

        try:
            return self._parse_veri(seriler, baslangic, bitis, items)
        except Exception as e:
            return _error("VERI_FORMAT_HATASI", f"API yanıtı ayrıştırılamadı: {e}")

    def _parse_veri(
        self, seriler: list[str], baslangic: str, bitis: str, items: list[dict]
    ) -> dict:
        """Parse EVDS items into structured output.

        Sorts items by date, filters out rows where ALL value columns are null
        (EVDS returns rows with null values before data is published), and
        converts columns to proper types.
        """
        df = pd.DataFrame(items)

        # Drop metadata columns before type conversion
        df = df.drop(columns=[c for c in ("UNIXTIME", "YEARWEEK") if c in df.columns])

        # Find date column
        tarih_col = "Tarih" if "Tarih" in df.columns else df.columns[0]

        df[tarih_col] = _tarih_parse(df[tarih_col])

        # Sort by date (EVDS doesn't guarantee ordering)
        df = df.sort_values(tarih_col).reset_index(drop=True)

        # Convert numeric columns
        value_cols = [c for c in df.columns if c != tarih_col]
        for col in value_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Filter out rows where ALL value columns are null (pre-publication rows)
        null_rows_dropped = 0
        if value_cols:
            null_rows_dropped = int(df[value_cols].isna().all(axis=1).sum())
            df = df.dropna(subset=value_cols, how="all")

        veri = []
        for _, row in df.iterrows():
            entry = {"tarih": row[tarih_col].strftime("%Y-%m-%d")}
            for col in value_cols:
                val = row[col]
                entry[col] = round(float(val), 4) if pd.notna(val) else None
            veri.append(entry)

        result: dict = {
            "seriler": seriler,
            "tarih_araligi": [baslangic, bitis],
            "gozlem_sayisi": len(veri),
            "veri": veri,
        }
        if null_rows_dropped > 0:
            result["uyari"] = f"{null_rows_dropped} null gözlem filtrelendi (veri henüz yayınlanmamış olabilir)"
        return result
