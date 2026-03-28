"""Tests for analysis functions — deterministic outputs from known inputs."""

import numpy as np
import pandas as pd
import pytest

from evds_mcp.analysis import (
    analiz_ozet,
    analiz_degisim,
    analiz_korelasyon,
    analiz_ols,
    analiz_arima,
)


@pytest.fixture
def sample_df():
    """Monthly CPI-like data, 48 observations."""
    dates = pd.date_range("2020-01-01", periods=48, freq="MS")
    np.random.seed(42)
    values = 100 + np.cumsum(np.random.normal(2, 1, 48))
    return pd.DataFrame({"TP.FG.J0": values}, index=dates)


@pytest.fixture
def two_series_df(sample_df):
    """Two correlated series."""
    np.random.seed(42)
    df = sample_df.copy()
    df["TP.DK.USD.A"] = df["TP.FG.J0"] * 0.5 + np.random.normal(0, 1, 48)
    return df


# --- Özet ---

class TestOzet:
    def test_keys(self, sample_df):
        result = analiz_ozet(sample_df)
        seri = result["TP.FG.J0"]
        for key in ("ortalama", "std", "min", "min_tarih", "max", "max_tarih",
                     "son_deger", "trend", "gozlem"):
            assert key in seri, f"Missing key: {key}"

    def test_deterministic(self, sample_df):
        r1 = analiz_ozet(sample_df)
        r2 = analiz_ozet(sample_df)
        assert r1 == r2

    def test_gozlem_count(self, sample_df):
        result = analiz_ozet(sample_df)
        assert result["TP.FG.J0"]["gozlem"] == 48


# --- Değişim ---

class TestDegisim:
    def test_aylik_keys(self, sample_df):
        result = analiz_degisim(sample_df, periyot="aylik")
        seri = result["TP.FG.J0"]
        assert "degisim_serisi" in seri
        assert "son_degisim" in seri

    def test_yillik(self, sample_df):
        result = analiz_degisim(sample_df, periyot="yillik")
        assert len(result["TP.FG.J0"]["degisim_serisi"]) == 36

    def test_deterministic(self, sample_df):
        r1 = analiz_degisim(sample_df, periyot="aylik")
        r2 = analiz_degisim(sample_df, periyot="aylik")
        assert r1 == r2


# --- Korelasyon ---

class TestKorelasyon:
    def test_keys(self, two_series_df):
        result = analiz_korelasyon(two_series_df)
        assert "matris" in result
        assert "yorumlar" in result

    def test_yorum_structure(self, two_series_df):
        result = analiz_korelasyon(two_series_df)
        yorum = result["yorumlar"][0]
        for key in ("seri1", "seri2", "r", "guc", "yon"):
            assert key in yorum

    def test_positive_correlation(self, two_series_df):
        result = analiz_korelasyon(two_series_df)
        assert result["yorumlar"][0]["yon"] == "pozitif"


# --- OLS ---

class TestOLS:
    def test_keys(self, two_series_df):
        result = analiz_ols(
            two_series_df, bagimli="TP.FG.J0"
        )
        for key in ("r_kare", "duzeltilmis_r_kare", "f_istatistigi",
                     "f_p_degeri", "katsayilar", "p_degerleri",
                     "standart_hatalar", "durbin_watson", "gozlem"):
            assert key in result, f"Missing key: {key}"

    def test_no_model_object(self, two_series_df):
        result = analiz_ols(two_series_df, bagimli="TP.FG.J0")
        assert "model" not in result

    def test_deterministic(self, two_series_df):
        r1 = analiz_ols(two_series_df, bagimli="TP.FG.J0")
        r2 = analiz_ols(two_series_df, bagimli="TP.FG.J0")
        assert r1 == r2


# --- ARIMA ---

class TestARIMA:
    def test_keys(self, sample_df):
        result = analiz_arima(sample_df["TP.FG.J0"], tahmin_donemi=6, mevsimsel=False)
        for key in ("order", "aic", "bic", "tahmin"):
            assert key in result, f"Missing key: {key}"

    def test_tahmin_length(self, sample_df):
        result = analiz_arima(sample_df["TP.FG.J0"], tahmin_donemi=6, mevsimsel=False)
        assert len(result["tahmin"]) == 6

    def test_tahmin_entry_keys(self, sample_df):
        result = analiz_arima(sample_df["TP.FG.J0"], tahmin_donemi=3, mevsimsel=False)
        entry = result["tahmin"][0]
        for key in ("tarih", "deger", "alt", "ust"):
            assert key in entry

    def test_no_model_object(self, sample_df):
        result = analiz_arima(sample_df["TP.FG.J0"], tahmin_donemi=3, mevsimsel=False)
        assert "model" not in result


# --- Özet template ---

class TestOzetTemplate:
    def test_ozet_str(self, sample_df):
        from evds_mcp.analysis import ozet_template
        sonuc = analiz_ozet(sample_df)
        text = ozet_template("ozet", {"TP.FG.J0": sonuc["TP.FG.J0"]})
        assert "son=" in text
        assert "ort=" in text
