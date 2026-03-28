"""Tests for EVDS API client."""

import httpx
import pytest
import respx

from evds_mcp.api import EVDSClient

BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis"


@pytest.fixture
def client():
    return EVDSClient(api_key="test-key")


@respx.mock
@pytest.mark.asyncio
async def test_request_sends_key_header(client):
    """API key sent in 'key' header."""
    route = respx.get(f"{BASE}/categories/type=json").mock(
        return_value=httpx.Response(200, json=[{"KATEGORI_ID": 1}])
    )
    result = await client.kategorileri_getir()
    assert route.called
    assert route.calls[0].request.headers["key"] == "test-key"


@respx.mock
@pytest.mark.asyncio
async def test_403_returns_api_key_gecersiz(client):
    """HTTP 403 → structured error with kod=API_KEY_GECERSIZ."""
    respx.get(f"{BASE}/categories/type=json").mock(
        return_value=httpx.Response(403)
    )
    result = await client.kategorileri_getir()
    assert result["hata"] is True
    assert result["kod"] == "API_KEY_GECERSIZ"


@respx.mock
@pytest.mark.asyncio
async def test_404_returns_seri_bulunamadi(client):
    """HTTP 404 → structured error."""
    respx.get(url__startswith=f"{BASE}/series=").mock(
        return_value=httpx.Response(404)
    )
    result = await client.veri_cek(["TP.INVALID"], "01-01-2024", "01-03-2026")
    assert result["hata"] is True
    assert result["kod"] == "SERI_BULUNAMADI"


@respx.mock
@pytest.mark.asyncio
async def test_timeout_retries_then_errors(client, monkeypatch):
    """Timeout → retries 3 times → BAGLANTI_HATASI."""
    import asyncio

    async def noop_sleep(_):
        pass

    monkeypatch.setattr(asyncio, "sleep", noop_sleep)
    route = respx.get(f"{BASE}/categories/type=json").mock(
        side_effect=httpx.ConnectTimeout("timeout")
    )
    result = await client.kategorileri_getir()
    assert result["hata"] is True
    assert result["kod"] == "BAGLANTI_HATASI"
    assert route.call_count == 3


@respx.mock
@pytest.mark.asyncio
async def test_empty_items_returns_veri_yok(client):
    """API returns 200 but no items → VERI_YOK."""
    respx.get(url__startswith=f"{BASE}/series=").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = await client.veri_cek(["TP.FG.J0"], "01-01-2030", "01-03-2030")
    assert result["hata"] is True
    assert result["kod"] == "VERI_YOK"


DATAGROUPS_RESPONSE = [
    {
        "DATAGROUP_CODE": "bie_tukfiy",
        "DATAGROUP_NAME_TR": "Tüketici Fiyat Endeksi",
        "FREQUENCY_STR": "Aylık",
        "DATASOURCE_TR": "TÜİK",
    },
    {
        "DATAGROUP_CODE": "bie_ufefiy",
        "DATAGROUP_NAME_TR": "Üretici Fiyat Endeksi",
        "FREQUENCY_STR": "Aylık",
        "DATASOURCE_TR": "TÜİK",
    },
]

SERIES_RESPONSE = [
    {
        "SERIE_CODE": "TP.FG.J0",
        "SERIE_NAME_TR": "TÜFE - Genel (2003=100)",
        "FREQUENCY_STR": "Aylık",
        "START_DATE": "01-01-2004",
        "END_DATE": "01-03-2026",
    },
    {
        "SERIE_CODE": "TP.FG.J1",
        "SERIE_NAME_TR": "TÜFE - Gıda",
        "FREQUENCY_STR": "Aylık",
        "START_DATE": "01-01-2004",
        "END_DATE": "01-03-2026",
    },
]


@respx.mock
@pytest.mark.asyncio
async def test_seri_ara_searches_groups_and_series(client):
    """seri_ara chains: datagroups → serieList, filters by keyword."""
    respx.get(f"{BASE}/datagroups/mode=0&type=json").mock(
        return_value=httpx.Response(200, json=DATAGROUPS_RESPONSE)
    )
    respx.get(f"{BASE}/serieList/code=bie_tukfiy&type=json").mock(
        return_value=httpx.Response(200, json=SERIES_RESPONSE)
    )

    result = await client.seri_ara("tüfe")
    assert "sonuclar" in result
    assert result["toplam"] >= 1
    assert any(s["seri_kodu"] == "TP.FG.J0" for s in result["sonuclar"])


@respx.mock
@pytest.mark.asyncio
async def test_seri_ara_no_match(client):
    """No matching groups → empty results."""
    respx.get(f"{BASE}/datagroups/mode=0&type=json").mock(
        return_value=httpx.Response(200, json=DATAGROUPS_RESPONSE)
    )
    result = await client.seri_ara("xyz_nonexistent")
    assert result["toplam"] == 0
    assert result["sonuclar"] == []
