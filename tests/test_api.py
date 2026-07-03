"""EVDSClient HTTP davranışı testleri — retry, hata kodları, cache (respx ile)."""

import httpx
import pytest
import respx

from evds_mcp.api import BASE_URL, EVDSClient


@pytest.fixture(autouse=True)
def hizli_backoff(monkeypatch):
    monkeypatch.setattr("evds_mcp.api.BACKOFF_BASE", 0.0)


@pytest.fixture
def client():
    return EVDSClient("test-key")


@respx.mock
async def test_403_api_key_hatasi(client):
    respx.get(f"{BASE_URL}/categories/type=json").mock(return_value=httpx.Response(403))
    sonuc = await client.kategorileri_getir()
    assert sonuc["hata"] is True
    assert sonuc["kod"] == "API_KEY_GECERSIZ"


@respx.mock
async def test_500_sonrasi_retry_basarili(client):
    route = respx.get(f"{BASE_URL}/categories/type=json")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json=[{"CATEGORY_ID": 1}]),
    ]
    sonuc = await client.kategorileri_getir()
    assert sonuc == [{"CATEGORY_ID": 1}]
    assert route.call_count == 2


@respx.mock
async def test_gecersiz_json_yaniti(client):
    # EVDS bazen HTTP 200 ile HTML hata sayfası döner
    respx.get(f"{BASE_URL}/categories/type=json").mock(
        return_value=httpx.Response(200, text="<html>Bakım</html>")
    )
    sonuc = await client.kategorileri_getir()
    assert sonuc["hata"] is True
    assert sonuc["kod"] == "GECERSIZ_YANIT"


@respx.mock
async def test_veri_gruplari_cache(client):
    route = respx.get(f"{BASE_URL}/datagroups/mode=0&type=json").mock(
        return_value=httpx.Response(200, json=[{"DATAGROUP_CODE": "bie_x"}])
    )
    await client.veri_gruplari()
    await client.veri_gruplari()
    assert route.call_count == 1


@respx.mock
async def test_seri_listesi_cache(client):
    route = respx.get(f"{BASE_URL}/serieList/code=bie_x&type=json").mock(
        return_value=httpx.Response(200, json=[{"SERIE_CODE": "TP.X"}])
    )
    await client.seri_listesi("bie_x")
    await client.seri_listesi("bie_x")
    assert route.call_count == 1


@respx.mock
async def test_populer_arama_api_cagirmaz(client):
    # Popüler kısayol tam eşleşince hiç HTTP isteği atılmamalı
    sonuc = await client.seri_ara("dolar")
    assert sonuc["toplam"] == 1
    assert sonuc["sonuclar"][0]["seri_kodu"] == "TP.DK.USD.A"


@respx.mock
async def test_seri_bul(client):
    respx.get(f"{BASE_URL}/datagroups/mode=0&type=json").mock(
        return_value=httpx.Response(200, json=[
            {"DATAGROUP_CODE": "bie_a", "FREQUENCY_STR": "AYLIK", "DATASOURCE": "TCMB"},
            {"DATAGROUP_CODE": "bie_b", "FREQUENCY_STR": "GUNLUK", "DATASOURCE": "TCMB"},
        ])
    )
    respx.get(f"{BASE_URL}/serieList/code=bie_a&type=json").mock(
        return_value=httpx.Response(200, json=[{"SERIE_CODE": "TP.Y"}])
    )
    respx.get(f"{BASE_URL}/serieList/code=bie_b&type=json").mock(
        return_value=httpx.Response(200, json=[
            {"SERIE_CODE": "TP.X", "SERIE_NAME": "Test Serisi", "START_DATE": "01-01-2000"}
        ])
    )
    sonuc = await client.seri_bul("TP.X")
    assert sonuc["seri_adi"] == "Test Serisi"
    assert sonuc["frekans"] == "GUNLUK"


@respx.mock
async def test_seri_bul_bulunamadi(client):
    respx.get(f"{BASE_URL}/datagroups/mode=0&type=json").mock(
        return_value=httpx.Response(200, json=[{"DATAGROUP_CODE": "bie_a"}])
    )
    respx.get(f"{BASE_URL}/serieList/code=bie_a&type=json").mock(
        return_value=httpx.Response(200, json=[{"SERIE_CODE": "TP.Y"}])
    )
    sonuc = await client.seri_bul("TP.YOK")
    assert sonuc["hata"] is True
    assert sonuc["kod"] == "SERI_BULUNAMADI"


@respx.mock
async def test_veri_cek_bozuk_tarih_yapisal_hata_doner(client):
    # Ayrıştırılamayan yanıt traceback değil yapısal hata dönmeli
    respx.get(url__startswith=f"{BASE_URL}/series=").mock(
        return_value=httpx.Response(200, json={"items": [{"Tarih": {"garip": 1}, "TP_X": "1"}]})
    )
    sonuc = await client.veri_cek(["TP.X"], "01-01-2023", "31-12-2023")
    # dict Tarih değeri str()'lenince fallback coerce NaT üretir → strftime patlar → yakalanır
    assert sonuc.get("hata") is True
    assert sonuc["kod"] == "VERI_FORMAT_HATASI"
