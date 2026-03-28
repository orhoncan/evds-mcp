"""Deterministic analysis functions — fixed-schema dict output, no model objects."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def analiz_ozet(df: pd.DataFrame) -> dict[str, dict]:
    """Descriptive statistics for each column."""
    sonuclar = {}
    for col in df.columns:
        seri = df[col].dropna()
        if len(seri) == 0:
            continue

        # Trend detection
        if len(seri) >= 12:
            son_12 = seri.tail(12)
            ilk_6 = son_12.head(6).mean()
            son_6 = son_12.tail(6).mean()
            if ilk_6 != 0:
                degisim = (son_6 - ilk_6) / abs(ilk_6) * 100
                if degisim > 5:
                    trend = "Yükseliş"
                elif degisim < -5:
                    trend = "Düşüş"
                else:
                    trend = "Yatay"
            else:
                trend = "Yatay"
        else:
            trend = "Yetersiz veri"

        sonuclar[col] = {
            "ortalama": round(float(seri.mean()), 4),
            "std": round(float(seri.std()), 4),
            "min": round(float(seri.min()), 4),
            "min_tarih": seri.idxmin().strftime("%Y-%m-%d"),
            "max": round(float(seri.max()), 4),
            "max_tarih": seri.idxmax().strftime("%Y-%m-%d"),
            "son_deger": round(float(seri.iloc[-1]), 4),
            "trend": trend,
            "gozlem": len(seri),
        }
    return sonuclar


def analiz_degisim(df: pd.DataFrame, periyot: str = "aylik") -> dict[str, dict]:
    """Percentage change calculation."""
    lag = {"aylik": 1, "yillik": 12, "donemsel": 3}.get(periyot, 1)
    sonuclar = {}
    for col in df.columns:
        seri = df[col].dropna()
        degisim = seri.pct_change(periods=lag).dropna() * 100
        degisim_serisi = {
            d.strftime("%Y-%m-%d"): round(float(v), 4)
            for d, v in degisim.items()
        }
        sonuclar[col] = {
            "degisim_serisi": degisim_serisi,
            "son_degisim": round(float(degisim.iloc[-1]), 4) if len(degisim) > 0 else None,
        }
    return sonuclar


def analiz_korelasyon(df: pd.DataFrame, metot: str = "pearson") -> dict:
    """Correlation matrix with verbal interpretation."""
    corr = df.corr(method=metot)

    matris = {}
    for col in corr.columns:
        matris[col] = {c: round(float(corr.loc[col, c]), 4) for c in corr.columns}

    yorumlar = []
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            r = float(corr.iloc[i, j])
            abs_r = abs(r)
            if abs_r >= 0.8:
                guc = "çok güçlü"
            elif abs_r >= 0.6:
                guc = "güçlü"
            elif abs_r >= 0.4:
                guc = "orta"
            elif abs_r >= 0.2:
                guc = "zayıf"
            else:
                guc = "ihmal edilebilir"

            yorumlar.append({
                "seri1": corr.columns[i],
                "seri2": corr.columns[j],
                "r": round(r, 4),
                "guc": guc,
                "yon": "pozitif" if r > 0 else "negatif",
            })

    return {"matris": matris, "yorumlar": yorumlar}


def analiz_ols(df: pd.DataFrame, bagimli: str) -> dict:
    """OLS regression — returns numeric results only."""
    try:
        import statsmodels.api as sm
    except ImportError:
        return {"hata": True, "kod": "ANALIZ_HATASI", "mesaj": "statsmodels paketi yüklü değil."}

    data = df.dropna()
    y = data[bagimli]
    X = data.drop(columns=[bagimli])

    X = sm.add_constant(X)
    model = sm.OLS(y, X).fit()
    dw = float(sm.stats.stattools.durbin_watson(model.resid))

    return {
        "r_kare": round(float(model.rsquared), 4),
        "duzeltilmis_r_kare": round(float(model.rsquared_adj), 4),
        "f_istatistigi": round(float(model.fvalue), 4),
        "f_p_degeri": round(float(model.f_pvalue), 4),
        "katsayilar": {k: round(float(v), 4) for k, v in model.params.items()},
        "p_degerleri": {k: round(float(v), 4) for k, v in model.pvalues.items()},
        "standart_hatalar": {k: round(float(v), 4) for k, v in model.bse.items()},
        "durbin_watson": round(dw, 4),
        "gozlem": int(model.nobs),
    }


def analiz_arima(
    y: pd.Series,
    tahmin_donemi: int = 12,
    mevsimsel: bool = True,
    m: int = 12,
) -> dict:
    """ARIMA/SARIMA — returns numeric results only."""
    try:
        from pmdarima import auto_arima
    except ImportError:
        return {"hata": True, "kod": "ANALIZ_HATASI", "mesaj": "pmdarima paketi yüklü değil."}

    y_clean = y.dropna()
    model = auto_arima(
        y_clean,
        start_p=0, start_q=0, max_p=5, max_q=5,
        seasonal=mevsimsel, m=m if mevsimsel else 1,
        start_P=0, start_Q=0, max_P=2, max_Q=2,
        d=None, D=None, trace=False, error_action="ignore",
        suppress_warnings=True, stepwise=True, information_criterion="aic",
    )

    tahmin_vals, guven = model.predict(
        n_periods=tahmin_donemi, return_conf_int=True, alpha=0.05
    )

    son_tarih = y_clean.index[-1]
    freq = pd.infer_freq(y_clean.index) or "MS"
    tahmin_tarihleri = pd.date_range(start=son_tarih, periods=tahmin_donemi + 1, freq=freq)[1:]

    # tahmin_vals may be a Series with DatetimeIndex — use positional access
    tahmin_array = np.asarray(tahmin_vals)
    tahmin = []
    for i in range(tahmin_donemi):
        tahmin.append({
            "tarih": tahmin_tarihleri[i].strftime("%Y-%m-%d"),
            "deger": round(float(tahmin_array[i]), 4),
            "alt": round(float(guven[i, 0]), 4),
            "ust": round(float(guven[i, 1]), 4),
        })

    return {
        "order": model.order,
        "seasonal_order": model.seasonal_order if mevsimsel else None,
        "aic": round(float(model.aic()), 4),
        "bic": round(float(model.bic()), 4),
        "tahmin": tahmin,
    }


def ozet_template(analiz_turu: str, sonuc: dict) -> str:
    """Generate deterministic one-line summary from analysis results."""
    if analiz_turu == "ozet":
        parts = []
        for seri, s in sonuc.items():
            parts.append(f"{seri}: son={s['son_deger']}, ort={s['ortalama']}, trend={s['trend']}")
        return "; ".join(parts)

    if analiz_turu == "degisim":
        parts = []
        for seri, s in sonuc.items():
            parts.append(f"{seri}: son değişim=%{s['son_degisim']}")
        return "; ".join(parts)

    if analiz_turu == "korelasyon":
        parts = []
        for y in sonuc.get("yorumlar", []):
            if y["guc"] != "ihmal edilebilir":
                parts.append(f"{y['seri1']}↔{y['seri2']}: r={y['r']} ({y['guc']} {y['yon']})")
        return "; ".join(parts) if parts else "Anlamlı korelasyon bulunamadı."

    if analiz_turu == "ols":
        return f"R²={sonuc['r_kare']}, F={sonuc['f_istatistigi']} (p={sonuc['f_p_degeri']}), DW={sonuc['durbin_watson']}"

    if analiz_turu == "arima":
        model_str = f"ARIMA{sonuc['order']}"
        if sonuc.get("seasonal_order"):
            model_str += f"x{sonuc['seasonal_order']}"
        son = sonuc["tahmin"][-1] if sonuc["tahmin"] else {}
        return f"{model_str}, AIC={sonuc['aic']}, son tahmin: {son.get('deger', '?')}"

    return ""
