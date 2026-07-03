"""Analiz fonksiyonları testleri."""

import numpy as np
import pandas as pd

from evds_mcp.analysis import (
    analiz_baglam,
    analiz_degisim,
    analiz_korelasyon,
    analiz_ols,
    analiz_ozet,
    ozet_template,
)


def ornek_df(n=24, kolonlar=("TP_A",)):
    idx = pd.date_range("2023-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(42)
    data = {k: np.linspace(100, 200, n) + rng.normal(0, 1, n) for k in kolonlar}
    return pd.DataFrame(data, index=idx)


def test_ozet():
    sonuc = analiz_ozet(ornek_df())
    s = sonuc["TP_A"]
    assert s["gozlem"] == 24
    assert s["trend"] == "Yükseliş"
    assert "min_tarih" in s


def test_degisim():
    sonuc = analiz_degisim(ornek_df(), periyot="aylik")
    assert sonuc["TP_A"]["son_degisim"] is not None
    assert len(sonuc["TP_A"]["degisim_serisi"]) == 23


def test_korelasyon():
    df = ornek_df(kolonlar=("TP_A", "TP_B"))
    sonuc = analiz_korelasyon(df)
    assert sonuc["matris"]["TP_A"]["TP_A"] == 1.0
    assert len(sonuc["yorumlar"]) == 1


def test_ols_gecerli():
    df = ornek_df(kolonlar=("TP_A", "TP_B"))
    sonuc = analiz_ols(df, bagimli="TP_A")
    assert "r_kare" in sonuc
    assert sonuc["gozlem"] == 24


def test_ols_bagimli_yoksa_yapisal_hata():
    sonuc = analiz_ols(ornek_df(), bagimli="TP.OLMAYAN")
    assert sonuc["hata"] is True
    assert "TP.OLMAYAN" in sonuc["mesaj"]


def test_ols_tek_seri_yapisal_hata():
    sonuc = analiz_ols(ornek_df(), bagimli="TP_A")
    assert sonuc["hata"] is True


def test_baglam():
    sonuc = analiz_baglam(ornek_df())
    assert sonuc["trend"] == "yükseliş"
    assert sonuc["yoy"] is not None
    assert "uyari" in sonuc


def test_baglam_yetersiz_veri():
    df = ornek_df(n=1)
    sonuc = analiz_baglam(df)
    assert sonuc["hata"] is True


def test_ozet_template_baglam():
    sonuc = analiz_baglam(ornek_df())
    metin = ozet_template("baglam", sonuc)
    assert "trend=" in metin
