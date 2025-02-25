import os
# Desactivar TorchScript y forzar TTS a aceptar la licencia vía variable de entorno
os.environ["TORCH_JIT"] = "0"
os.environ["COQUI_TOS_AGREED"] = "1"  # Ajusta si tu TTS usa otro nombre de variable (p.ej. "TTS_ACCEPT_EULA")

import streamlit as st
from TTS.api import TTS
from pydub import AudioSegment
import fitz  # PyMuPDF
import docx
import io
import torch


# Detectar el dispositivo (GPU o CPU)
device = "cuda" if torch.cuda.is_available() else "cpu"

# Inicializar TTS con el modelo multilingüe xtts_v2
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=(device == "cuda"))

# Verificar si el modelo soporta múltiples hablantes
try:
    speakers = tts.speakers
except AttributeError:
    speakers = ["default"]

st.title("Conversor de Texto a Audio")

# Entrada de texto o archivo para extraer el contenido
text_input = st.text_area("Pega tu texto aquí:")
uploaded_file = st.file_uploader("O sube un archivo (txt, pdf, docx):", type=["txt", "pdf", "docx"])

# Opciones de idioma
language_options = {
    "Español (España)": "es",
    "Alemán": "de",
    "Inglés": "en",
    "Chino": "zh"
}
language_choice = st.selectbox("Selecciona el idioma:", list(language_options.keys()))

# Selección de hablante
speaker_choice = st.selectbox("Selecciona el hablante:", speakers)

# Control de velocidad de lectura
speed = st.slider("Velocidad de lectura", 0.5, 2.0, 1.0)

# Control de tono
tone = st.slider("Tono (semitonos)", -12, 12, 0)

# Control de entonación
intonation = st.slider("Entonación (semitonos)", -12, 12, 0)

# Subir archivo de voz para clonación (opcional)
speaker_wav = st.file_uploader("Sube un archivo de voz para clonación (opcional):", type=["wav"])

# Botones para activar y desactivar clonación de voz
cloning_active = st.checkbox("Activar clonación de voz", value=False)

def extract_text_from_pdf(file):
    try:
        pdf_document = fitz.open(stream=io.BytesIO(file.getvalue()))
        return "\n".join([page.get_text() for page in pdf_document])
    except Exception as e:
        st.error(f"Error al procesar el PDF: {e}")
        return ""

def extract_text_from_word(file):
    try:
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        st.error(f"Error al procesar el Word: {e}")
        return ""

def change_pitch(sound, semitones):
    new_sample_rate = int(sound.frame_rate * (2.0 ** (semitones / 12.0)))
    pitched_sound = sound._spawn(sound.raw_data, overrides={'frame_rate': new_sample_rate})
    return pitched_sound.set_frame_rate(sound.frame_rate)

def convert_text_to_audio(text, output_file, speaker, speaker_wav, language, speed=1.0, tone=0, intonation=0):
    speaker_wav_path = None
    if speaker_wav is not None:
        speaker_wav_path = "temp_speaker.wav"
        with open(speaker_wav_path, "wb") as f:
            f.write(speaker_wav.getbuffer())
    
    try:
        tts.tts_to_file(
            text=text,
            speaker=speaker,
            speaker_wav=speaker_wav_path if cloning_active else None,
            language=language,
            file_path="temp.wav"
        )
    except Exception as e:
        st.error(f"Error al generar el audio TTS: {e}")
        return False
    
    try:
        audio = AudioSegment.from_file("temp.wav")
    except Exception as e:
        st.error(f"Error al cargar el archivo temporal de audio: {e}")
        return False

    if abs(speed - 1.0) > 0.01:
        try:
            audio = audio.speedup(playback_speed=speed)
        except Exception as e:
            st.error(f"Error al ajustar la velocidad del audio: {e}")
            return False

    total_pitch = tone + intonation
    if total_pitch != 0:
        try:
            audio = change_pitch(audio, total_pitch)
        except Exception as e:
            st.error(f"Error al ajustar el tono del audio: {e}")
            return False

    try:
        audio.export(output_file, format="mp3", bitrate="192k")
    except Exception as e:
        st.error(f"Error al exportar el audio a MP3: {e}")
        return False

    return True

if st.button("Convertir a Audio"):
    text = text_input.strip() if text_input.strip() else None
    if not text and uploaded_file:
        if uploaded_file.type == "text/plain":
            text = io.StringIO(uploaded_file.getvalue().decode("utf-8")).read()
        elif uploaded_file.type == "application/pdf":
            text = extract_text_from_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = extract_text_from_word(uploaded_file)

    if text:
        output_file = "output_audio.mp3"
        success = convert_text_to_audio(
            text,
            output_file,
            speaker=speaker_choice,
            speaker_wav=speaker_wav,
            language=language_options[language_choice],
            speed=speed,
            tone=tone,
            intonation=intonation
        )
        if success:
            st.success("Audio generado exitosamente.")
            st.audio(output_file, format="audio/mp3")  # Reproductor de audio integrado
            with open(output_file, "rb") as f:
                st.download_button("Descargar Audio", data=f, file_name="output_audio.mp3", mime="audio/mp3")
        else:
            st.error("No se pudo generar el audio correctamente.")
    else:
        st.error("No se detectó texto válido.")

for file in ["temp.wav", "temp_speaker.wav"]:
    if os.path.exists(file):
        os.remove(file)