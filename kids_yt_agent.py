import os
import requests
import asyncio
import edge_tts
from gtts import gTTS
from groq import Groq
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, ColorClip
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import random
import re

# ---------------------------------------------------------
# STEP 1: AI Script & Scene Prompts Generation (Groq)
# ---------------------------------------------------------
def generate_cinematic_story(language="English", is_short=False):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    if is_short:
        duration_desc = "90-second fast-paced viral YouTube Short with an engaging hook"
        scene_count = 3
    else:
        duration_desc = "1-hour long epic moral bedtime story compilation featuring Trisha and Tiya"
        scene_count = 10

    prompt = f"""
    You are a master 3D animation director and storyteller for kids channel 'Trisha and Tiya Tales Time'.
    Create a {duration_desc} in {language}.
    Break the story down into {scene_count} distinct visual scenes.
    
    Provide output strictly in this format:
    TOPIC: <story title slug>
    TITLE: <YouTube SEO Title with Emojis and #Shorts if short>
    DESCRIPTION: <Kid-friendly description with hashtags>
    TAGS: <Comma separated tags>
    
    SCENE 1 PROMPT: <Detailed 3D Pixar style visual description for image generation>
    SCENE 1 SCRIPT: <Detailed narration text for scene 1>
    
    (Continue for all scenes up to SCENE {scene_count})
    """
    
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openai/gpt-oss-20b",
        max_tokens=4096
    )
    return response.choices[0].message.content

# ---------------------------------------------------------
# STEP 2: Voiceover Generation
# ---------------------------------------------------------
async def generate_voiceover(text, language="English", output_audio="voiceover.mp3"):
    try:
        voice = "en-US-AnaNeural" if language == "English" else "hi-IN-SwaraNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_audio)
    except Exception as e:
        print(f"Edge-TTS failed: {e}. Using gTTS fallback...")
        lang_code = 'en' if language == 'English' else 'hi'
        tts = gTTS(text=text, lang=lang_code, slow=False)
        tts.save(output_audio)

# ---------------------------------------------------------
# STEP 3: AI Art Frame Generation (Pollinations AI)
# ---------------------------------------------------------
def generate_ai_art_image(prompt_text, output_filename="scene.png", is_short=False):
    width = 1080 if is_short else 1920
    height = 1920 if is_short else 1080
    
    enhanced_prompt = f"3D Pixar style cute cartoon, vibrant colors, cinematic lighting, children book illustration: {prompt_text}"
    encoded_prompt = requests.utils.quote(enhanced_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"
    
    try:
        res = requests.get(url, timeout=30)
        if res.status_code == 200:
            with open(output_filename, "wb") as f:
                f.write(res.content)
            return output_filename
    except Exception as e:
        print(f"AI Image generation error: {e}")
    
    backup = ColorClip(size=(width, height), color=(255, 182, 193), duration=5)
    backup.save_frame(output_filename)
    return output_filename

# ---------------------------------------------------------
# STEP 4: Render Video (1 Hour Long or 90s Short)
# ---------------------------------------------------------
def render_cinematic_video(audio_path="voiceover.mp3", image_prompts=None, output_path="final_video.mp4", is_short=False):
    audio = AudioFileClip(audio_path)
    total_audio_duration = audio.duration
    
    if not image_prompts:
        image_prompts = ["Cute cartoon magical adventure forest with Trisha and Tiya"]
        
    scene_duration = max(5, total_audio_duration / len(image_prompts))
    
    clips = []
    for i, prompt in enumerate(image_prompts):
        img_file = f"scene_{i}.png"
        generate_ai_art_image(prompt, img_file, is_short=is_short)
        clip = ImageClip(img_file).set_duration(scene_duration)
        clips.append(clip)
        
    visual_track = concatenate_videoclips(clips, method="compose")
    
    target_duration = 90 if is_short else max(3600, total_audio_duration)
    
    if visual_track.duration < target_duration:
        visual_track = visual_track.loop(duration=target_duration)
    else:
        visual_track = visual_track.subclip(0, target_duration)
        
    final_clip = visual_track.set_audio(audio)
    final_clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=2
    )

# ---------------------------------------------------------
# STEP 5: Smart YouTube Queue Scheduler (`publishAt`)
# ---------------------------------------------------------
def upload_to_youtube(video_path, title, description, tags_list, language="English", is_short=False):
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("YT_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YT_CLIENT_ID"),
        client_secret=os.getenv("YT_CLIENT_SECRET")
    )
    
    youtube = build("youtube", "v3", credentials=creds)
    
    future_offset_hours = random.randint(2, 24)
    publish_at_time = datetime.utcnow() + timedelta(hours=future_offset_hours)
    publish_at_iso = publish_at_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags_list,
            "categoryId": "1"
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at_iso,
            "selfDeclaredMadeForKids": True
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"Successfully queued [{language} | {'Short' if is_short else 'Long'}] for {publish_at_iso}! Video ID: {response.get('id')}")

# ---------------------------------------------------------
# MAIN ROTATIONAL ORCHESTRATOR
# ---------------------------------------------------------
if __name__ == "__main__":
    current_hour = datetime.utcnow().hour
    
    language = "Hindi" if current_hour % 4 == 0 else "English"
    is_short = True if current_hour % 2 == 0 else False
    
    print(f"Starting 2-Hour Cycle -> Generating {'Short (90s)' if is_short else 'Long-form (1 Hour)'} in {language}...")
    
    ai_output = generate_cinematic_story(language=language, is_short=is_short)
    
    topic = "trisha_tiya_story"
    title = "Trisha and Tiya Tales Time"
    description = "Magical bedtime stories for kids."
    tags = ["cartoon", "kids stories", "Trisha and Tiya", "Bedtime Stories"]
    
    prompts = []
    full_script = ""
    
    for line in ai_output.split("\n"):
        if "TOPIC:" in line:
            topic = re.sub(r'[^a-zA-Z0-9]', '_', line.replace("TOPIC:", "").strip()).lower()
        elif "TITLE:" in line:
            title = line.replace("TITLE:", "").strip()
        elif "DESCRIPTION:" in line:
            description = line.replace("DESCRIPTION:", "").strip()
        elif "TAGS:" in line:
            tags = [t.strip() for t in line.replace("TAGS:", "").split(",")]
        elif "PROMPT:" in line:
            prompts.append(line.split("PROMPT:")[1].strip())
        elif "SCRIPT:" in line:
            full_script += line.split("SCRIPT:")[1].strip() + " "

    if not prompts:
        prompts = ["A magical cartoon world with two cute kids named Trisha and Tiya"]
    if not full_script.strip():
        full_script = ai_output

    file_name = f"{topic}_{language.lower()}_{'short' if is_short else 'long'}.mp4"

    print("1. Generating Voiceover...")
    asyncio.run(generate_voiceover(full_script, language=language))

    print("2. Generating AI Art Scenes & Rendering Video...")
    render_cinematic_video(audio_path="voiceover.mp3", image_prompts=prompts, output_path=file_name, is_short=is_short)

    print(f"3. Uploading & Auto-Scheduling on YouTube ({language})...")
    upload_to_youtube(file_name, title, description, tags, language=language, is_short=is_short)
    print("DONE! Cycle finished successfully.")
