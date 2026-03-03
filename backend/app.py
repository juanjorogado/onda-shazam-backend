#!/usr/bin/env python3
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import httpx
from datetime import datetime
from acrcloud.recognizer import ACRCloudRecognizer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ACR_CONFIG = {
    "host": "ap-southeast-1.api.acrcloud.com",
    "access_key": "409edc00cbff342f0960a6e82d872028",
    "access_secret": "3ETYsb5Aud9wZ2KoiFH2rZgk1ZYT2Fv9Xj42phnk",
    "timeout": 10,
}

ANYTYPE_API_KEY = "FwdYEb4HaiBYlUBiCjJsdo8cYbTGoWRibB3CdRctJTs="
ANYTYPE_SPACE_ID = "bafyreidsjaufkmqy2qbhxytumdfeijc4i5u37yqizbshdziuu6xuvg5rne"

acr = ACRCloudRecognizer(ACR_CONFIG)


def get_apple_music_link(metadata: dict) -> str:
    try:
        if metadata.get("spotify"):
            return metadata["spotify"].get("external_urls", {}).get("spotify", "")
        if metadata.get("apple_music"):
            return metadata["apple_music"].get("url", "")
        return ""
    except Exception:
        return ""


@app.post("/recognize")
async def recognize_song(file: UploadFile = File(...)):
    try:
        audio_data = await file.read()
        result = acr.recognize_by_filebuffer(audio_data, 0)

        if result["status"]["code"] != 0:
            return {"success": False, "message": "No song recognized"}

        metadata = result["metadata"]["music"][0]

        song_info = {
            "title": metadata.get("title", "Unknown"),
            "artist": metadata.get("artists", [{}])[0].get("name", "Unknown"),
            "album": metadata.get("album", {}).get("name", ""),
            "year": metadata.get("release_date", "")[:4] if metadata.get("release_date") else "",
            "cover_url": metadata.get("album", {}).get("images", [{}])[0].get("url", ""),
            "apple_music_link": get_apple_music_link(metadata),
        }

        return {"success": True, "song": song_info}

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/save-to-anytype")
async def save_to_anytype(data: dict):
    try:
        song = data.get("song", {})
        station = data.get("station", "Unknown")

        payload = {
            "name": f"{song.get('title', 'Unknown')} - {song.get('artist', 'Unknown')}",
            "icon": "🎵",
            "type_key": "canci\u00f3n",
            "properties": {
                "date": datetime.now().isoformat(),
                "station": station,
                "song": song.get("title", ""),
                "artist": song.get("artist", ""),
                "album": song.get("album", ""),
                "year": song.get("year", ""),
                "cover": song.get("cover_url", ""),
                "appleMusicLink": song.get("apple_music_link", ""),
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
