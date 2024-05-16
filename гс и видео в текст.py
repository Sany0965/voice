import hashlib
import requests
import logging
from telebot import TeleBot, types
from spellchecker import SpellChecker
import soundfile as sf
import speech_recognition as sr
from moviepy.editor import VideoFileClip, AudioFileClip
import os
import asyncio

TELEGRAM_KEY = 'токен от бот фазер'
VOICE_LANGUAGE = 'ru-RU'
MAX_MESSAGE_SIZE = 50 * 1024 * 1024
MAX_MESSAGE_DURATION = 120

bot = TeleBot(TELEGRAM_KEY)

spell = SpellChecker()

greeted_users = set()

@bot.message_handler(commands=['start'])
def start_prompt(message):
    greeted_users.add(message.chat.id)  # Добавляем id пользователя в множество greeted_users
    user_name = message.from_user.first_name
    reply = ("Добро пожаловать, {user_name}! Я могу превратить голосовое сообщение в текст😎.\n"
             "Просто перешли мне голосовое сообщение, и я пришлю расшифровку.\n"
             "И даже Telegram premium не нужен!\n"
             "<b>☢Голосовые сообщения и видеосообщения не больше 2 минут!</b>").format(user_name=user_name)
    keyboard = types.InlineKeyboardMarkup()
    url_button = types.InlineKeyboardButton(text="🟠Dev", url="https://t.me/pizzaway")
    keyboard.add(url_button)
    bot.send_message(message.chat.id, reply, parse_mode="HTML", reply_markup=keyboard)


@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    received_message = bot.reply_to(message, "🤖Аудиосообщение принято!Ждите!")
    asyncio.run(remove_message(received_message, 2))
    process_audio_message(message)

@bot.message_handler(content_types=['video_note'])
def handle_video_message(message):
    received_message = bot.reply_to(message, "🤖Видеозаметка принята!Ждите!")
    asyncio.run(remove_message(received_message, 2))
    process_video_message(message)

async def remove_message(message, delay):
    await asyncio.sleep(delay)
    bot.delete_message(message.chat.id, message.message_id)

def process_audio_message(message):
    data = message.voice
    if (data.file_size > MAX_MESSAGE_SIZE) or (data.duration > MAX_MESSAGE_DURATION):
        reply = f"Голосовое сообщение слишком большое. Максимальная длительность: {MAX_MESSAGE_DURATION} сек."
        return bot.reply_to(message, reply)

    file_url = "https://api.telegram.org/file/bot{}/{}".format(
        bot.token,
        bot.get_file(data.file_id).file_path
    )

    file_path = download_file(file_url)
    convert_to_pcm16(file_path)
    text = process_audio_file("new.wav")

    if not text:
        return bot.reply_to(message, "Бот🤖:Извините, сообщение не распознано!.")
    
    text_with_punctuation = add_punctuation(text)
    bot.reply_to(message, f"🤖Расшифровка: {text_with_punctuation}")
    cleanup_files(["new.wav", "voice_message.ogg"])

def process_video_message(message):
    data = message.video_note
    if (data.file_size > MAX_MESSAGE_SIZE):
        reply = f"Видеозаметка слишком большая. Максимальный размер: {MAX_MESSAGE_SIZE} байт."
        return bot.reply_to(message, reply)

    file_url = "https://api.telegram.org/file/bot{}/{}".format(
        bot.token,
        bot.get_file(data.file_id).file_path
    )

    file_path = download_video(file_url)
    convert_to_ogg(file_path)
    convert_to_wav("new.ogg")
    text = process_audio_file("new.wav")

    if not text:
        return bot.reply_to(message, "Бот🤖:Извините, сообщение не распознано!.")
    
    text_with_punctuation = add_punctuation(text)
    bot.reply_to(message, f"🤖Расшифровка видеозаметки: {text_with_punctuation}")
    cleanup_files(["new.ogg", "new.wav"])

def download_file(file_url):
    file_path = "voice_message.ogg"
    with open(file_path, 'wb') as f:
        response = requests.get(file_url)
        f.write(response.content)
    return file_path

def download_video(file_url):
    file_path = "video_note.mp4"
    with open(file_path, 'wb') as f:
        response = requests.get(file_url)
        f.write(response.content)
    return file_path

def convert_to_pcm16(file_path):
    data, samplerate = sf.read(file_path)
    sf.write('new.wav', data, samplerate, subtype='PCM_16')

def convert_to_ogg(file_path):
    video = VideoFileClip(file_path)
    video.audio.write_audiofile("new.ogg", codec='libvorbis')

def convert_to_wav(file_path):
    clip = AudioFileClip(file_path)
    clip.write_audiofile("new.wav", codec='pcm_s16le', fps=44100)

def process_audio_file(file_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio_data = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio_data, language=VOICE_LANGUAGE)
        return text
    except sr.UnknownValueError:
        return None

def add_punctuation(text):
    corrected_text = spell.correction(text)
    if corrected_text is None:
        return text
    
    if not corrected_text.endswith('.'):
        corrected_text += '.'
    return corrected_text

def cleanup_files(files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)

bot.polling()