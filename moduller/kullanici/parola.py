"""Parola ozetleme. Parolanin kendisi hicbir yerde saklanmaz."""

import hashlib
import hmac
import secrets

_N = 2**15
_R = 8
_P = 1
_AZAMI_BELLEK = 128 * 1024 * 1024
_TUZ_BOYUTU = 16


def _hesapla(parola: str, tuz: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        parola.encode("utf-8"), salt=tuz, n=n, r=r, p=p, maxmem=_AZAMI_BELLEK
    )


def parola_ozetle(parola: str) -> str:
    """Parolayi rastgele tuzla ozetler. Ayarlar ozetle birlikte saklanir."""
    tuz = secrets.token_bytes(_TUZ_BOYUTU)
    ozet = _hesapla(parola, tuz, _N, _R, _P)
    return f"scrypt${_N}${_R}${_P}${tuz.hex()}${ozet.hex()}"


def parola_dogru_mu(parola: str, kayitli_ozet: str) -> bool:
    """Parolayi kayitli ozetle karsilastirir. Bozuk kayit her zaman reddedilir."""
    try:
        yontem, n, r, p, tuz, ozet = kayitli_ozet.split("$")
        if yontem != "scrypt":
            return False
        hesaplanan = _hesapla(parola, bytes.fromhex(tuz), int(n), int(r), int(p))
        return hmac.compare_digest(hesaplanan, bytes.fromhex(ozet))
    except ValueError:
        return False
