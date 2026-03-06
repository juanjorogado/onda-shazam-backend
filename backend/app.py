#!/usr/bin/env python3
import base64
import hashlib
import hmac
import time
import json
import httpx
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tu host original era ap-southeast-1, lo uso aquí
ACR_CONFIG = {
    "host": "ap-southeast-1.api.acrcloud.com",
    "access_key": "409edc00cbff342f0960a6e82d872028",
    "access_secret": "3ETYsb5Aud9wZ2KoiFH2rZgk1ZYT2Fv9Xj42phnk",
}

ANYTYPE_API_KEY = "FwdYEb4HaiBYlUBiCjJsdo8cYbTGoWRibB3CdRctJTs="
ANYTYPE_SPACE_ID = "bafyreidsjaufkmqy2qbhxytumdfeijc4i5u37yqizbshdziuu6xuvg5rne"


def sign_request(secret: str, method: str, uri: str, access_key: str, data_type: str, sig_version: str, timestamp: str) -> str:
    string_to_sign = f"{method}\n{uri}\n{access_key}\n{data_type}\n{sig_version}\n{timestamp}"
    return base64.b64encode(
        hmac.new(secret.encode('ascii'), string_to_sign.encode('ascii'), digestmod=hashlib.sha1).digest()
    ).decode('ascii')


def get_external_link(metadata: dict, service: str) -> str:
    try:
        ext = metadata.get("external_metadata", {}).get(service, {})
        if service == "spotify":
            return ext.get("track", {}).get("external_urls", {}).get("spotify", "")
        if service == "apple_music":
            return ext.get("url", "")
        return ""
    except Exception:
        return ""


@app.post("/recognize")
async def recognize_song(file: UploadFile = File(...)):
    try:
        audio_data = await file.read()
        print(f"Received audio file: {file.filename}, size: {len(audio_data)} bytes")
        
        timestamp = str(int(time.time()))
        signature = sign_request(
            ACR_CONFIG["access_secret"],
            "POST",
            "/v1/identify",
            ACR_CONFIG["access_key"],
            "audio",
            "1",
            timestamp
        )
        
        # Usar el host correcto
        url = f"https://{ACR_CONFIG['host']}/v1/identify"
        print(f"Making request to: {url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                files={
                    "sample": (file.filename or "audio.webm", audio_data, "audio/webm")
                },
                data={
                    "access_key": ACR_CONFIG["access_key"],
                    "sample_bytes": len(audio_data),
                    "timestamp": timestamp,
                    "signature": signature,
                    "data_type": "audio",
                    "signature_version": "1"
                },
                timeout=30.0
            )
        
        print(f"Response status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result)[:500]}")
        
        if result.get("status", {}).get("code") != 0:
            msg = result.get("status", {}).get("msg", "No song recognized")
            return {"success": False, "message": msg}
        
        metadata = result["metadata"]["music"][0]
        
        song_info = {
            "title": metadata.get("title", "Unknown"),
            "artist": metadata.get("artists", [{}])[0].get("name", "Unknown"),
            "album": metadata.get("album", {}).get("name", ""),
            "year": metadata.get("release_date", "")[:4] if metadata.get("release_date") else "",
            "cover_url": metadata.get("album", {}).get("images", [{}])[0].get("url", ""),
            "apple_music_link": get_external_link(metadata, "apple_music"),
        }
        
        return {"success": True, "song": song_info}
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
        return {"success": False, "message": str(e)}


@app.post("/save-to-anytype")
async def save_to_anytype(
    song_title: str = Form(...),
    song_artist: str = Form(...),
    song_album: str = Form(""),
    song_year: str = Form(""),
    song_cover: str = Form(""),
    song_apple_music_link: str = Form(""),
    station: str = Form(...)
):
    try:
        payload = {
            "name": f"{song_title} - {song_artist}",
            "icon": "🎵",
            "type_key": "canción",
            "properties": {
                "date": time.strftime("%Y-%m-%d"),
                "station": station,
                "song": song_title,
                "artist": song_artist,
                "album": song_album,
                "year": song_year,
                "cover": song_cover,
                "appleMusicLink": song_apple_music_link,
            },
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:31009/v1/spaces/{ANYTYPE_SPACE_ID}/objects",
                headers={
                    "Authorization": f"Bearer {ANYTYPE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        
        if response.status_code in (200, 201):
            return {"success": True}
        else:
            return {"success": False, "message": response.text}
            
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok"}
