import tweepy
import random
import os
import json
import requests

# API credentials from GitHub Secrets
API_KEY = os.environ["X_API_KEY"]
API_SECRET = os.environ["X_API_SECRET"]
ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = os.environ["X_ACCESS_TOKEN_SECRET"]
HF_TOKEN = os.environ["HF_TOKEN"]
PEXELS_KEY = os.environ["PEXELS_KEY"]

# Hugging Face API
HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1"

# Authenticate X API (kept for potential future use, but not used now)
print("Authenticating X API")
try:
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
except Exception as e:
    print(f"X authentication failed: {e}, proceeding without posting")

# Topics and emojis
topics = ["self_improvement", "studying", "fun_facts", "ai_tools", "macos_tips"]
emojis = {
    "self_improvement": "🌱",
    "studying": "📚",
    "fun_facts": "✨",
    "ai_tools": "💡",
    "macos_tips": "🍎"
}

# Track subtopics
HISTORY_FILE = "history.txt"

def load_history():
    default_history = {topic: [] for topic in topics}
    if not os.path.exists(HISTORY_FILE):
        print(f"{HISTORY_FILE} not found, initializing with default")
        return default_history
    with open(HISTORY_FILE, "r") as f:
        content = f.read().strip()
        if not content:
            print(f"{HISTORY_FILE} is empty, initializing with default")
            return default_history
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {HISTORY_FILE}: {e}, resetting to default")
            return default_history

def save_history(history):
    print(f"Saving history to {HISTORY_FILE}")
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def query_hf(prompt):
    print(f"Sending HF query: {prompt[:50]}...")
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": f"[INST] {prompt} [/INST]",
        "parameters": {"max_new_tokens": 300, "temperature": 0.7}
    }
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            text = response.json()[0]["generated_text"].split("[/INST]")[-1].strip()
            print(f"HF response: {text[:50]}...")
            return text
        print(f"HF API error: {response.status_code}, {response.text}")
        return None
    except Exception as e:
        print(f"HF query failed: {e}")
        return None

def fetch_pexels_image(query):
    print(f"Fetching Pexels image for query: {query}")
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    headers = {"Authorization": PEXELS_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            photos = response.json().get("photos", [])
            if photos:
                img_url = photos[0]["src"]["medium"]
                img_data = requests.get(img_url).content
                img_path = f"temp_{random.randint(1000, 9999)}.jpg"
                with open(img_path, "wb") as f:
                    f.write(img_data)
                print(f"Pexels image saved: {img_path}")
                return img_path
            print("No photos found for query")
            return None
        print(f"Pexels API error: {response.status_code}, {response.text}")
        return None
    except Exception as e:
        print(f"Pexels fetch failed: {e}")
        return None

def generate_content(topic):
    print(f"Generating content for topic: {topic}")
    history = load_history()
    used_subtopics = history.get(topic, [])

    # Generate subtopic
    for _ in range(3):
        prompt = (
            f"Suggest a unique subtopic for {topic.replace('_', ' ')}. "
            f"Avoid: {', '.join(used_subtopics) or 'none'}. "
            "Return one subtopic name, max 30 chars, no explanation."
        )
        subtopic = query_hf(prompt)
        # Truncate to 30 chars
        if subtopic:
            subtopic = subtopic[:30]
        print(f"Generated subtopic attempt: {subtopic}")
        if subtopic and subtopic not in used_subtopics and len(subtopic) < 30:
            break
    else:
        subtopic = used_subtopics[-1] if used_subtopics else f"{topic}_general"
        print(f"Subtopic fallback: {subtopic}")

    # Generate thread
    prompt = (
        f"Write a 3-tweet thread on {subtopic} for {topic.replace('_', ' ')}. "
        "Each tweet <280 chars, based on verified info, 1-2 hashtags. "
        f"Main tweet starts with 🧵, parts use 1️⃣, 2️⃣, 3️⃣. Include {emojis[topic]}. "
        "Output exactly 4 parts (main + 3 follow-ups) separated by ||. "
        "Do NOT use single output or '/'. Example: 🧵main||1️⃣part1||2️⃣part2||3️⃣part3."
    )
    thread_text = query_hf(prompt)
    if not thread_text:
        print("Thread generation failed, using fallback")
        # Fallback thread
        thread_parts = [
            f"🧵 Kickstart {topic.replace('_', ' ')} today! {emojis[topic]} #Growth",
            f"1️⃣ Set one small goal daily. Consistency wins! {emojis[topic]} #Mindset",
            f"2️⃣ Reflect on progress weekly. Adjust as needed. {emojis[topic]} #SelfImprovement",
            f"3️⃣ Share your tips below! Let’s grow together. {emojis[topic]} #Community"
        ]
    else:
        thread_parts = [p.strip() for p in thread_text.split("||")]
        print(f"Thread parts: {thread_parts}")
        if len(thread_parts) not in [3, 4]:
            print(f"Invalid thread format: {thread_parts}, using fallback")
            # Fallback thread
            thread_parts = [
                f"🧵 Kickstart {topic.replace('_', ' ')} today! {emojis[topic]} #Growth",
                f"1️⃣ Set one small goal daily. Consistency wins! {emojis[topic]} #Mindset",
                f"2️⃣ Reflect on progress weekly. Adjust as needed. {emojis[topic]} #SelfImprovement",
                f"3️⃣ Share your tips below! Let’s grow together. {emojis[topic]} #Community"
            ]

    # Generate image keywords
    prompt = (
        f"Suggest 3 image keywords for {subtopic} ({topic.replace('_', ' ')}). "
        "Output: keyword1,keyword2,keyword3"
    )
    keywords_text = query_hf(prompt) or f"{topic},photo,image"
    # Clean and split keywords
    keywords = [k.strip().split('. ')[-1] for k in keywords_text.split('\n') if k.strip()]
    if len(keywords) < 3:
        keywords = keywords + [topic, "photo", "image"][:3 - len(keywords)]
    keywords = keywords[:3]
    print(f"Image keywords: {keywords}")

    # Update history
    used_subtopics.append(subtopic)
    history[topic] = used_subtopics[-10:]
    save_history(history)

    return {
        "main_tweet": thread_parts[0],
        "thread": thread_parts[1:] if len(thread_parts) > 1 else [],
        "image_keywords": keywords,
        "topic": topic,
        "subtopic": subtopic
    }

def post_thread():
    print("Starting post_thread")
    # Load or initialize topic index
    index_file = "topic_index.txt"
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            topic_index = int(f.read().strip())
    else:
        topic_index = 0
    print(f"Topic index: {topic_index}")

    topic = topics[topic_index]
    topic_index = (topic_index + 1) % len(topics)

    post = generate_content(topic)
    if not post or any(len(t) > 280 for t in [post["main_tweet"]] + post["thread"]):
        print("Invalid content, skipping...")
        return

    try:
        # Fetch images (for keywords, though manual posting may skip images)
        image_urls = []
        for i in range(min(len([post["main_tweet"]] + post["thread"]), 4)):
            keyword = post["image_keywords"][i % len(post["image_keywords"])]
            img_path = fetch_pexels_image(keyword)
            print(f"Image fetch for {keyword}: {img_path}")
            if img_path and os.path.exists(img_path):
                image_urls.append(f"Pexels image for {keyword}: {img_path}")
                os.remove(img_path)
            else:
                image_urls.append(f"No image for {keyword}")
                print(f"Image fetch failed for keyword: {keyword}")

        # Save thread to threads.txt
        output_file = "threads.txt"
        with open(output_file, "a") as f:
            f.write(f"--- Thread {topic_index} ---\n")
            f.write(f"Topic: {post['topic']}\n")
            f.write(f"Subtopic: {post['subtopic']}\n")
            f.write(f"Main Tweet: {post['main_tweet']}\n")
            for i, part in enumerate(post['thread']):
                f.write(f"Part {i+1}: {part}\n")
            for i, url in enumerate(image_urls):
                f.write(f"Image {i+1}: {url}\n")
            f.write("\n")
        print(f"Saved thread to {output_file}")

        # Save topic index
        print(f"Saving topic index: {topic_index}")
        with open(index_file, "w") as f:
            f.write(str(topic_index))

    except Exception as e:
        print(f"Saving thread failed: {e}")
        raise

if __name__ == "__main__":
    post_thread()
