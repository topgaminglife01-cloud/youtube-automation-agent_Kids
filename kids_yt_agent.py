import os
import requests
import asyncio
import edge_tts
from gtts import gTTS
from groq import Groq
from moviepy.editor import VideoFileClip, AudioFileClip, ColorClip
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import re

# ---------------------------------------------------------
# STEP 1: AI Script & Metadata Generation (Groq)
# ---------------------------------------------------------
def generate_kids_content(language="English", is_short=False):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    duration_type = "30-second viral Short" if is_short else "10-minute long moral bedtime story for kids featuring two characters named Trisha and Tiya"
    
    prompt = f"""
    You are a professional children's storyteller and YouTube SEO expert for the channel 'Trisha and Tiya Tales Time'.
    Create a {duration_type} in {language}.
    
    Provide your output strictly in this format:
    TOPIC: <Short catchy topic name for file naming>
    TITLE: <SEO optimized YouTube title with emojis and #Shorts if short>
    DESCRIPTION: <Kid-friendly description with hashtags and keywords>
    TAGS: <Comma separated tags>
    KEYWORD: <Single background search keyword like cartoon forest, magical castle, cute animals>
    SCRIPT: <The full voiceover narration script>
    """
    
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openai/gpt-oss-20b",
    )
    return response.choices[0].message.content

# ---------------------------------------------------------
# STEP 2: Multi-Language Voiceover with gTTS Fallback
# ---------------------------------------------------------
async def generate_voiceover(text, language="English", output_audio="voiceover.mp3"):
    try:
        voice = "en-US-AnaNeural" if language == "English" else "hi-IN-SwaraNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_audio)
    except Exception as e:
        print(f"Edge-TTS failed: {e}. Switching to gTTS fallback...")
    
    if not os.path.exists(output_audio) or os.path.getsize(output_audio) == 0:
        print("Using gTTS fallback for voiceover generation...")
        lang_code = 'en' if language == 'English' else 'hi'
        tts = gTTS(text=text, lang=lang_code, slow=False)
        tts.save(output_audio)

# ---------------------------------------------------------
# STEP 3: Fetch Stock Animation/Background Footage
# ---------------------------------------------------------
def download_background(query, output_filename="background.mp4"):
    api_key = os.getenv("PIXABAY_API_KEY")
    url = f"https://pixabay.com/api/videos/?key={api_key}&q={query}&per_page=3&video_type=film"
    
    try:
        res = requests.get(url).json()
        if "hits" in res and len(res["hits"]) > 0:
            video_url = res["hits"][0]["videos"]["medium"]["url"]
            with open(output_filename, "wb") as f:
                f.write(requests.get(video_url).content)
            print(f"Downloaded video for: {query}")
            return
    except Exception as e:
        print(f"API fetch error: {e}")
    
    print("Using fallback solid backdrop...")
    backup = ColorClip(size=(1080, 1920), color=(255, 182, 193), duration=30)
    backup.write_videofile(output_filename, fps=24, codec="libx264")

# ---------------------------------------------------------
# STEP 4: Render Video (Long-form >10 mins or Short)
# ---------------------------------------------------------
def render_video(audio_path="voiceover.mp3", output_path="final_video.mp4", is_short=False):
    audio = AudioFileClip(audio_path)
    download_background("cartoon magic forest animation")
    
    base_clip = VideoFileClip("background.mp4")
    
    if is_short:
        video = base_clip.subclip(0, min(60, audio.duration))
        if video.duration < audio.duration:
            video = video.loop(duration=audio.duration)
    else:
        target_duration = max(600, audio.duration)
        video = base_clip.loop(duration=target_duration)
        
    final_clip = video.set_audio(audio)
    final_clip.write_videofile(
        output_path, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac",
        threads=2
    )

# ---------------------------------------------------------
# MAIN ORCHESTRATOR
# ---------------------------------------------------------
if __name__ == "__main__":
    language = os.getenv("VIDEO_LANGUAGE", "English")
    is_short = os.getenv("IS_SHORT", "false").lower() == "true"
    
    print(f"Generating {'Short' if is_short else 'Long-form (10+ min)'} video in {language}...")
    
    ai_raw = generate_kids_content(language=language, is_short=is_short)
    
    topic = "trisha_tiya_story"
    title = "Trisha and Tiya Tales Time"
    description = "Fun stories for kids!"
    tags = ["cartoon", "kids", "stories", "Trisha and Tiya"]
    keyword = "cartoon magic"
    script = ai_raw
    
    for line in ai_raw.split("\n"):
        if "TOPIC:" in line:
            raw_topic = line.replace("TOPIC:", "").strip()
            topic = re.sub(r'[^a-zA-Z0-9]', '_', raw_topic).lower()
        elif "TITLE:" in line:
            title = line.replace("TITLE:", "").strip()
        elif "DESCRIPTION:" in line:
            description = line.replace("DESCRIPTION:", "").strip()
        elif "TAGS:" in line:
            tags = [t.strip() for t in line.replace("TAGS:", "").split(",")]
        elif "KEYWORD:" in line:
            keyword = line.replace("KEYWORD:", "").strip()
        elif "SCRIPT:" in line:
            script = line.replace("SCRIPT:", "").strip()

    file_name = f"{topic}_{language.lower()}.mp4"

    print(f"1. Generating Voiceover in {language}...")
    asyncio.run(generate_voiceover(script, language=language))

    print(f"2. Rendering Video ({file_name})...")
    render_video(output_path=file_name, is_short=is_short)

    print(f"DONE! Generated file: {file_name}")
