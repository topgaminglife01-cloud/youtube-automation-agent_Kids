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
import re

# ---------------------------------------------------------
# STEP 1: AI Script & Scene Prompts Generation (Groq)
# ---------------------------------------------------------
def generate_cinematic_story(language="English"):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = f"""
    You are a master 3D animation director and storyteller for kids channel 'Trisha and Tiya Tales Time'.
    Create a 10-minute moral bedtime story script featuring two cartoon girls named Trisha and Tiya in {language}.
    Break the story down into 5 distinct visual scenes.
    
    Provide output strictly in this format:
    TOPIC: <story title slug>
    TITLE: <YouTube SEO Title with Emojis>
    DESCRIPTION: <Kid-friendly description with hashtags>
    TAGS: <Comma separated tags>
    
    SCENE 1 PROMPT: <Detailed 3D Pixar style visual description for image generation>
    SCENE 1 SCRIPT: <Narration text for scene 1>
    
    SCENE 2 PROMPT: <Detailed 3D Pixar style visual description>
    SCENE 2 SCRIPT: <Narration text for scene 2>
    
    SCENE 3 PROMPT: <Detailed 3D Pixar style visual description>
    SCENE 3 SCRIPT: <Narration text for scene 3>
    
    SCENE 4 PROMPT: <Detailed 3D Pixar style visual description>
    SCENE 4 SCRIPT: <Narration text for scene 4>
    
    SCENE 5 PROMPT: <Detailed 3D Pixar style visual description>
    SCENE 5 SCRIPT: <Narration text for scene 5>
    """
    
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="openai/gpt-oss-20b",
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
def generate_ai_art_image(prompt_text, output_filename="scene.png"):
    enhanced_prompt = f"3D Pixar style cute cartoon, vibrant colors, cinematic lighting, high quality children book illustration: {prompt_text}"
    encoded_prompt = requests.utils.quote(enhanced_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true"
    
    try:
        res = requests.get(url, timeout=30)
        if res.status_code == 200:
            with open(output_filename, "wb") as f:
                f.write(res.content)
            return output_filename
    except Exception as e:
        print(f"AI Image generation error: {e}")
    
    backup = ColorClip(size=(1280, 720), color=(255, 182, 193), duration=5)
    backup.save_frame(output_filename)
    return output_filename

# ---------------------------------------------------------
# STEP 4: Render Cinematic Multi-Scene Video (>10 mins)
# ---------------------------------------------------------
def render_cinematic_video(audio_path="voiceover.mp3", image_prompts=None, output_path="final_video.mp4"):
    audio = AudioFileClip(audio_path)
    total_audio_duration = audio.duration
    
    if not image_prompts:
        image_prompts = ["Cute cartoon magical adventure forest with Trisha and Tiya"]
        
    scene_duration = max(10, total_audio_duration / len(image_prompts))
    
    clips = []
    for i, prompt in enumerate(image_prompts):
        img_file = f"scene_{i}.png"
        generate_ai_art_image(prompt, img_file)
        clip = ImageClip(img_file).set_duration(scene_duration)
        clips.append(clip)
        
    visual_track = concatenate_videoclips(clips, method="compose")
    target_duration = max(600, total_audio_duration)
    if visual_track.duration < target_duration:
        visual_track = visual_track.loop(duration=target_duration)
        
    final_clip = visual_track.set_audio(audio)
    final_clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=2
    )

# ---------------------------------------------------------
# STEP 5: YouTube Scheduled Upload (Private + publishAt)
# ---------------------------------------------------------
def upload_to_youtube(video_path, title, description, tags_list, language="English"):
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("YT_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YT_CLIENT_ID"),
        client_secret=os.getenv("YT_CLIENT_SECRET")
    )
    
    youtube = build("youtube", "v3", credentials=creds)
    
    # Calculate next empty date & target slot (5 AM for English, 5 PM for Hindi)
    now = datetime.utcnow()
    target_hour = 5 if language == "English" else 17
    
    scheduled_time = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if now >= scheduled_time:
        scheduled_time += timedelta(days=1)
        
    publish_at_iso = scheduled_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags_list,
            "categoryId": "1"
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at_iso,  # Automatically queues for the slot
            "selfDeclaredMadeForKids": True
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"Successfully scheduled [{language}] upload for {publish_at_iso}! Video ID: {response.get('id')}")

# ---------------------------------------------------------
# MAIN ORCHESTRATOR
# ---------------------------------------------------------
if __name__ == "__main__":
    language = os.getenv("VIDEO_LANGUAGE", "English")
    print(f"Generating Cinematic 3D Story in {language}...")
    
    ai_output = generate_cinematic_story(language=language)
    
    topic = "trisha_tiya_3d_adventure"
    title = "Trisha and Tiya 3D Cartoon Story"
    description = "Magical bedtime stories for kids."
    tags = ["cartoon", "3D animation", "kids stories", "Trisha and Tiya"]
    
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

    file_name = f"{topic}_{language.lower()}.mp4"

    print("1. Generating Voiceover...")
    asyncio.run(generate_voiceover(full_script, language=language))

    print("2. Generating AI Art Scenes & Rendering Cinematic Video...")
    render_cinematic_video(audio_path="voiceover.mp3", image_prompts=prompts, output_path=file_name)

    print(f"3. Uploading & Scheduling to YouTube ({language})...")
    upload_to_youtube(file_name, title, description, tags, language=language)
    print("DONE! Scheduled successfully.")
