from flask import Flask, request, jsonify
from flask_cors import CORS
import ShazamIO
import aiohttp
import asyncio
import os
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ANYTYPE_API_KEY = os.environ.get('ANYTYPE_API_KEY')
ANYTYPE_SPACE_ID = os.environ.get('ANYTYPE_SPACE_ID', 'bafyreidsjaufkmqy2qbhxytumdfefeijc4i5u37yqizbshdziuu6xuvg5rne')

ANYTYPE_HEADERS = {
    'Authorization': f'Bearer {ANYTYPE_API_KEY}',
    'Content-Type': 'application/json'
}

ANYTYPE_API_URL = 'https://api.anytype.io'

async def save_to_anytype(song_data: dict, station_name: str):
    """Guarda la canción en AnyType"""
    try:
        # Obtener fecha actual
        import datetime
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Preparar el objeto para AnyType
        # Nota: Necesitas crear un tipo "Canción" en AnyType primero
        object_payload = {
            "type": "song",  # Esto dependerá del type_key de tu objeto en AnyType
            "name": f"{song_data.get('title', 'Unknown')} - {song_data.get('artist', 'Unknown')}",
            "properties": {
                "fecha": current_date,
                "estacion": station_name,
                "cancion": song_data.get('title', ''),
                "artista": song_data.get('artist', ''),
                "album": song_data.get('album', ''),
                "ano": song_data.get('year', 0),
                "cover": song_data.get('cover', ''),
                "appleMusic": song_data.get('apple_music', '')
            }
        }
        
        async with aiohttp.ClientSession() as session:
            url = f"{ANYTYPE_API_URL}/v1/spaces/{ANYTYPE_SPACE_ID}/objects"
            async with session.post(url, json=object_payload, headers=ANYTYPE_HEADERS) as resp:
                if resp.status == 200:
                    logger.info(f"Canción guardada en AnyType: {song_data.get('title')}")
                    return True
                else:
                    logger.error(f"Error guardando en AnyType: {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"Error en save_to_anytype: {e}")
        return False

async def identify_song(audio_path: str, station_name: str):
    """Identifica la canción usando ShazamIO"""
    shazam = ShazamIO.ShazamIO()
    
    try:
        out = await shazam.recognize_song(audio_path)
        
        if out and len(out) > 0:
            track = out[0]
            
            # Extraer datos del track
            song_data = {
                'title': track.get('title', 'Unknown'),
                'artist': track.get('subtitle', 'Unknown'),
                'album': track.get('sectionMetadata', {}).get('caption', ''),
                'cover': '',
                'apple_music': '',
                'year': 0
            }
            
            # Obtener cover de imágenes
            if 'images' in track:
                song_data['cover'] = track['images'].get('coverart', '')
            
            # Obtener enlaces de Apple Music / Spotify
            if 'hub' in track:
                hub = track['hub']
                if 'options' in hub:
                    for option in hub['options']:
                        if 'actions' in option:
                            for action in option['actions']:
                                if action.get('type') == 'appleMusicopen':
                                    song_data['apple_music'] = action.get('uri', '')
                                    break
                                elif action.get('type') == 'spotifyopen':
                                    song_data['spotify'] = action.get('uri', '')
            
            # Extraer año de release date
            if 'sections' in track:
                for section in track['sections']:
                    if 'metadata' in section:
                        for meta in section['metadata']:
                            if meta.get('caption') == 'Released':
                                try:
                                    year = meta.get('text', '').split('-')[0]
                                    song_data['year'] = int(year)
                                except:
                                    pass
            
            # Guardar en AnyType
            await save_to_anytype(song_data, station_name)
            
            return song_data
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error identificando canción: {e}")
        return None

@app.route('/identify', methods=['POST'])
def identify_endpoint():
    """Endpoint para identificar canción"""
    if 'file' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['file']
    station_name = request.form.get('station', 'Unknown')
    
    # Guardar archivo temporalmente
    temp_path = '/tmp/audio.wav'
    audio_file.save(temp_path)
    
    # Ejecutar identificación
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(identify_song(temp_path, station_name))
    loop.close()
    
    if result:
        return jsonify(result)
    else:
        return jsonify({'error': 'Could not identify song'}), 404

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
