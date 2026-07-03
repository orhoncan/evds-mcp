"""_parse_veri ve _tarih_parse testleri — EVDS'nin frekansa göre değişen tarih formatları."""

import pandas as pd
import pytest

from evds_mcp.api import EVDSClient, _tarih_parse


@pytest.fixture
def client():
    return EVDSClient("test-key")


def parse(client, items, seriler=None):
    return client._parse_veri(seriler or ["TP.TEST"], "01-01-2023", "31-12-2023", items)


def test_gunluk_format(client):
    items = [
        {"Tarih": "05-01-2024", "TP_DK_USD_A": "29.64", "UNIXTIME": {"$numberLong": "1"}},
        {"Tarih": "04-01-2024", "TP_DK_USD_A": "29.50", "UNIXTIME": {"$numberLong": "2"}},
    ]
    sonuc = parse(client, items)
    assert sonuc["gozlem_sayisi"] == 2
    # sıralama: eski tarih önce
    assert sonuc["veri"][0]["tarih"] == "2024-01-04"
    assert sonuc["veri"][1]["TP_DK_USD_A"] == 29.64


def test_haftalik_format_yearweek_dusuruldu(client):
    items = [
        {"Tarih": "05-01-2024", "YEARWEEK": "2024-1", "TP_DK_USD_A": "29.64"},
    ]
    sonuc = parse(client, items)
    assert "YEARWEEK" not in sonuc["veri"][0]
    assert sonuc["veri"][0]["tarih"] == "2024-01-05"


def test_aylik_format(client):
    items = [
        {"Tarih": "2024-1", "TP_FG_J0": "100.5"},
        {"Tarih": "2024-12", "TP_FG_J0": "150.5"},
    ]
    sonuc = parse(client, items)
    assert sonuc["veri"][0]["tarih"] == "2024-01-01"
    assert sonuc["veri"][1]["tarih"] == "2024-12-01"


def test_ceyreklik_format(client):
    items = [
        {"Tarih": "2023-Q1", "TP_FG_J0": "1238.19"},
        {"Tarih": "2023-Q4", "TP_FG_J0": "1805.00"},
    ]
    sonuc = parse(client, items)
    assert sonuc["veri"][0]["tarih"] == "2023-01-01"
    assert sonuc["veri"][1]["tarih"] == "2023-10-01"


def test_alti_aylik_format(client):
    items = [
        {"Tarih": "2023-S1", "TP_FG_J0": "1277.80"},
        {"Tarih": "2023-S2", "TP_FG_J0": "1700.03"},
    ]
    sonuc = parse(client, items)
    assert sonuc["veri"][0]["tarih"] == "2023-01-01"
    assert sonuc["veri"][1]["tarih"] == "2023-07-01"


def test_yillik_format_int_tarih(client):
    # Yıllık frekansta EVDS Tarih alanını string değil int döner
    items = [
        {"Tarih": 2021, "TP_FG_J0": "561.61", "UNIXTIME": {"$numberLong": "1"}},
        {"Tarih": 2022, "TP_FG_J0": "967.71", "UNIXTIME": {"$numberLong": "2"}},
    ]
    sonuc = parse(client, items)
    assert sonuc["gozlem_sayisi"] == 2
    assert sonuc["veri"][0]["tarih"] == "2021-01-01"


def test_null_satirlar_filtrelenir_ve_uyari_doner(client):
    items = [
        {"Tarih": "2024-1", "TP_FG_J0": "100.5"},
        {"Tarih": "2024-2", "TP_FG_J0": None},
        {"Tarih": "2024-3", "TP_FG_J0": None},
    ]
    sonuc = parse(client, items)
    assert sonuc["gozlem_sayisi"] == 1
    assert "uyari" in sonuc
    assert "2 null" in sonuc["uyari"]


def test_kismi_null_satir_korunur(client):
    # İki seriden biri null ise satır düşürülmemeli
    items = [
        {"Tarih": "2024-1", "TP_A": "1.0", "TP_B": None},
        {"Tarih": "2024-2", "TP_A": "2.0", "TP_B": "3.0"},
    ]
    sonuc = parse(client, items, seriler=["TP.A", "TP.B"])
    assert sonuc["gozlem_sayisi"] == 2
    assert sonuc["veri"][0]["TP_B"] is None
    assert "uyari" not in sonuc


def test_tarih_parse_formatlari():
    assert _tarih_parse(pd.Series(["2023"])).iloc[0] == pd.Timestamp("2023-01-01")
    assert _tarih_parse(pd.Series(["2023-Q3"])).iloc[0] == pd.Timestamp("2023-07-01")
    assert _tarih_parse(pd.Series(["2023-S2"])).iloc[0] == pd.Timestamp("2023-07-01")
    assert _tarih_parse(pd.Series(["2023-7"])).iloc[0] == pd.Timestamp("2023-07-01")
    assert _tarih_parse(pd.Series(["15-07-2023"])).iloc[0] == pd.Timestamp("2023-07-15")
